#!/usr/bin/env python3
"""spellcode —— 源码拼写检查器。

设计只有一句话：**只在有把握的时候说话**。

宁可漏掉一个冷僻的错拼，也不要把哈希值、版本号、缩写当成错别字塞给你。
零配置文件，标准库实现，单文件。

用法：
    python spellcode.py                 # 检查当前目录
    python spellcode.py src tests       # 检查指定目录
    python spellcode.py --fix src       # 就地修正
    python spellcode.py --json src      # 机器可读输出

退出码：0 干净，2 有发现，1 出错。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# 错拼词典
# ---------------------------------------------------------------------------
# 只有一件事值得记在这里：**一个词的拼法唯一地对应另一个词**。
#
# 刻意不收的几类：
#   * 两三个字母的（`ba`、`teh` 之外的短词）—— 哈希片段和缩写太容易撞上
#   * 本身是合法英文词的（`dependant`、`throughout`）
#   * 是某个合法词前缀的（`delet`、`optio`）—— 复数/动词变形会被误伤
#
# 这张表是「信心」的来源，不是「覆盖率」的来源。

TYPOS: Dict[str, str] = {
    "accross": "across",
    "accomodate": "accommodate",
    "acheive": "achieve",
    "acheived": "achieved",
    "acknowlege": "acknowledge",
    "adress": "address",
    "adressed": "addressed",
    "agressive": "aggressive",
    "allign": "align",
    "alligned": "aligned",
    "ammount": "amount",
    "analagous": "analogous",
    "analize": "analyze",
    "apparant": "apparent",
    "appearence": "appearance",
    "applicaiton": "application",
    "appologies": "apologies",
    "arguement": "argument",
    "arguements": "arguments",
    "assigment": "assignment",
    "assigments": "assignments",
    "assocation": "association",
    "asychronous": "asynchronous",
    "asyncrounous": "asynchronous",
    "attribtue": "attribute",
    "authenication": "authentication",
    "authorizaiton": "authorization",
    "automaticaly": "automatically",
    "availabe": "available",
    "avaliable": "available",
    "backgroud": "background",
    "basicly": "basically",
    "beggining": "beginning",
    "begining": "beginning",
    "beleive": "believe",
    "beleived": "believed",
    "belive": "believe",
    "benifit": "benefit",
    "boundry": "boundary",
    "buidl": "build",
    "buisness": "business",
    "calcualte": "calculate",
    "calcualted": "calculated",
    "calender": "calendar",
    "cancelation": "cancellation",
    "caracter": "character",
    "catagory": "category",
    "cetrain": "certain",
    "challange": "challenge",
    "charachter": "character",
    "charcter": "character",
    "chekc": "check",
    "claer": "clear",
    "clietn": "client",
    "coefficent": "coefficient",
    "collecton": "collection",
    "colum": "column",
    "colummn": "column",
    "comamnd": "command",
    "comand": "command",
    "commadn": "command",
    "comming": "coming",
    "commited": "committed",
    "commnad": "command",
    "comparision": "comparison",
    "compatability": "compatibility",
    "compatable": "compatible",
    "completly": "completely",
    "componenet": "component",
    "componnent": "component",
    "concatinate": "concatenate",
    "concurency": "concurrency",
    "configration": "configuration",
    "configuartion": "configuration",
    "configuraton": "configuration",
    "conjuction": "conjunction",
    "connnection": "connection",
    "consistant": "consistent",
    "construtor": "constructor",
    "contian": "contain",
    "contians": "contains",
    "continous": "continuous",
    "continously": "continuously",
    "convertion": "conversion",
    "correclty": "correctly",
    "correcton": "correction",
    "correponding": "corresponding",
    "coudl": "could",
    "cricital": "critical",
    "currenly": "currently",
    "currnet": "current",
    "custome": "custom",
    "deafult": "default",
    "decison": "decision",
    "decription": "description",
    "defaut": "default",
    "definately": "definitely",
    "definitly": "definitely",
    "defintion": "definition",
    "delimeter": "delimiter",
    "dependancy": "dependency",
    "dependecies": "dependencies",
    "dependnecy": "dependency",
    "descibe": "describe",
    "descripton": "description",
    "deserialze": "deserialize",
    "destory": "destroy",
    "detial": "detail",
    "detials": "details",
    "developement": "development",
    "develpment": "development",
    "differnt": "different",
    "diffrent": "different",
    "dimention": "dimension",
    "directoy": "directory",
    "disapear": "disappear",
    "disbale": "disable",
    "disconect": "disconnect",
    "dispaly": "display",
    "docuemnt": "document",
    "documet": "document",
    "documnet": "document",
    "doenst": "doesn't",
    "ealier": "earlier",
    "eaxmple": "example",
    "efective": "effective",
    "efficent": "efficient",
    "embarass": "embarrass",
    "emited": "emitted",
    "enbale": "enable",
    "encdoing": "encoding",
    "encyption": "encryption",
    "endianess": "endianness",
    "enought": "enough",
    "enviornment": "environment",
    "enviroment": "environment",
    "equivelant": "equivalent",
    "errror": "error",
    "evalute": "evaluate",
    "excecute": "execute",
    "exectue": "execute",
    "exhaused": "exhausted",
    "existance": "existence",
    "explicite": "explicit",
    "explicitely": "explicitly",
    "expresion": "expression",
    "externa": "external",
    "faild": "failed",
    "failes": "fails",
    "falied": "failed",
    "familar": "familiar",
    "fileds": "fields",
    "finaly": "finally",
    "firts": "first",
    "flase": "false",
    "follwing": "following",
    "foramt": "format",
    "foriegn": "foreign",
    "formated": "formatted",
    "formating": "formatting",
    "foward": "forward",
    "frequecy": "frequency",
    "fucntion": "function",
    "funtion": "function",
    "functon": "function",
    "futher": "further",
    "garantee": "guarantee",
    "genarate": "generate",
    "generatd": "generated",
    "genereate": "generate",
    "glbal": "global",
    "goverment": "government",
    "grahpic": "graphic",
    "gruop": "group",
    "gurantee": "guarantee",
    "happend": "happened",
    "headr": "header",
    "heigth": "height",
    "heirarchy": "hierarchy",
    "higest": "highest",
    "hopefuly": "hopefully",
    "howver": "however",
    "identifer": "identifier",
    "identifed": "identified",
    "immediatly": "immediately",
    "implament": "implement",
    "implemenation": "implementation",
    "implemention": "implementation",
    "implmentation": "implementation",
    "incldue": "include",
    "inclue": "include",
    "incompatable": "incompatible",
    "inconsistant": "inconsistent",
    "independant": "independent",
    "indepedent": "independent",
    "indicies": "indices",
    "initail": "initial",
    "initialze": "initialize",
    "initilize": "initialize",
    "instanciate": "instantiate",
    "instanse": "instance",
    "interger": "integer",
    "interupt": "interrupt",
    "intial": "initial",
    "intialize": "initialize",
    "invalide": "invalid",
    "invokation": "invocation",
    "iteraton": "iteration",
    "itsself": "itself",
    "jsut": "just",
    "keyworkd": "keyword",
    "knwo": "know",
    "lanaguage": "language",
    "langauge": "language",
    "lauch": "launch",
    "lenght": "length",
    "libary": "library",
    "librairy": "library",
    "liek": "like",
    "lisence": "license",
    "lisense": "license",
    "listner": "listener",
    "locaion": "location",
    "loger": "logger",
    "maintainance": "maintenance",
    "maintenence": "maintenance",
    "managment": "management",
    "mananger": "manager",
    "maping": "mapping",
    "measurment": "measurement",
    "messsage": "message",
    "messgae": "message",
    "minimun": "minimum",
    "mininum": "minimum",
    "minumum": "minimum",
    "mispelled": "misspelled",
    "missleading": "misleading",
    "modfiy": "modify",
    "moduel": "module",
    "moudle": "module",
    "mutliple": "multiple",
    "multipel": "multiple",
    "neccessary": "necessary",
    "necesary": "necessary",
    "negitive": "negative",
    "neverthless": "nevertheless",
    "noticable": "noticeable",
    "notifcation": "notification",
    "occassion": "occasion",
    "occured": "occurred",
    "occurence": "occurrence",
    "occuring": "occurring",
    "ocurred": "occurred",
    "obviuos": "obvious",
    "offical": "official",
    "ommited": "omitted",
    "ommit": "omit",
    "omited": "omitted",
    "onyl": "only",
    "optmize": "optimize",
    "orginal": "original",
    "orignal": "original",
    "oustanding": "outstanding",
    "overide": "override",
    "overriden": "overridden",
    "overrride": "override",
    "paramater": "parameter",
    "paramter": "parameter",
    "parmeter": "parameter",
    "particualr": "particular",
    "passwrod": "password",
    "paticular": "particular",
    "perfer": "prefer",
    "perfrom": "perform",
    "perhpas": "perhaps",
    "permanant": "permanent",
    "persistend": "persistent",
    "persistant": "persistent",
    "placholder": "placeholder",
    "platfrom": "platform",
    "polciy": "policy",
    "posible": "possible",
    "postion": "position",
    "preceed": "precede",
    "prefered": "preferred",
    "preffer": "prefer",
    "prelimenary": "preliminary",
    "prepration": "preparation",
    "presense": "presence",
    "previos": "previous",
    "priorty": "priority",
    "priveledge": "privilege",
    "proccess": "process",
    "procces": "process",
    "propery": "property",
    "propety": "property",
    "proprty": "property",
    "protcol": "protocol",
    "psuedo": "pseudo",
    "publically": "publicly",
    "querry": "query",
    "quering": "querying",
    "recevie": "receive",
    "recieved": "received",
    "reciever": "receiver",
    "recieve": "receive",
    "recieves": "receives",
    "recieving": "receiving",
    "recomend": "recommend",
    "recomendation": "recommendation",
    "recursivly": "recursively",
    "refence": "reference",
    "refered": "referred",
    "refernece": "reference",
    "referrence": "reference",
    "regarless": "regardless",
    "registred": "registered",
    "registraton": "registration",
    "regsiter": "register",
    "relavent": "relevant",
    "relevent": "relevant",
    "remaing": "remaining",
    "remvoe": "remove",
    "repetion": "repetition",
    "reposiotry": "repository",
    "repositiory": "repository",
    "repostory": "repository",
    "requirment": "requirement",
    "requiremnt": "requirement",
    "resposne": "response",
    "responsibilty": "responsibility",
    "retreive": "retrieve",
    "retrive": "retrieve",
    "retrun": "return",
    "retun": "return",
    "reuslt": "result",
    "reuqest": "request",
    "reuqired": "required",
    "rquest": "request",
    "saftey": "safety",
    "scedule": "schedule",
    "scheduel": "schedule",
    "seach": "search",
    "seperate": "separate",
    "seperated": "separated",
    "seperately": "separately",
    "seperating": "separating",
    "seperator": "separator",
    "serailize": "serialize",
    "serialze": "serialize",
    "serivce": "service",
    "serveral": "several",
    "shoud": "should",
    "shoudl": "should",
    "signle": "single",
    "similiar": "similar",
    "simmilar": "similar",
    "simplfy": "simplify",
    "situtation": "situation",
    "souce": "source",
    "specifc": "specific",
    "specifiy": "specify",
    "speficied": "specified",
    "spliting": "splitting",
    "stanadard": "standard",
    "standar": "standard",
    "statment": "statement",
    "stauts": "status",
    "stoped": "stopped",
    "stucture": "structure",
    "sturcture": "structure",
    "subcribe": "subscribe",
    "succeded": "succeeded",
    "succes": "success",
    "succesful": "successful",
    "successfull": "successful",
    "sucess": "success",
    "supress": "suppress",
    "suppresed": "suppressed",
    "suppored": "supported",
    "supprot": "support",
    "suport": "support",
    "surfce": "surface",
    "swtich": "switch",
    "symetric": "symmetric",
    "synchonous": "synchronous",
    "syncronous": "synchronous",
    "syntex": "syntax",
    "sysmte": "system",
    "sytem": "system",
    "targert": "target",
    "teh": "the",
    "tempalte": "template",
    "temporarly": "temporarily",
    "thier": "their",
    "threshhold": "threshold",
    "tommorow": "tomorrow",
    "tranform": "transform",
    "transation": "transaction",
    "transfered": "transferred",
    "trasaction": "transaction",
    "truely": "truly",
    "udpate": "update",
    "unamed": "unnamed",
    "uncommited": "uncommitted",
    "undefiend": "undefined",
    "understnad": "understand",
    "unexpectd": "unexpected",
    "unfortunatly": "unfortunately",
    "unitialized": "uninitialized",
    "unknwon": "unknown",
    "unneccessary": "unnecessary",
    "upate": "update",
    "usefull": "useful",
    "usign": "using",
    "usualy": "usually",
    "utilty": "utility",
    "varable": "variable",
    "varaint": "variant",
    "varient": "variant",
    "verfiy": "verify",
    "verison": "version",
    "versoin": "version",
    "vlaue": "value",
    "wating": "waiting",
    "wether": "whether",
    "whcih": "which",
    "wiht": "with",
    "withing": "within",
    "wnat": "want",
    "woudl": "would",
    "wrapepr": "wrapper",
    "writen": "written",
    "writting": "writing",
    "yeild": "yield",
}

# 常见变形后缀。命中词典的只是词干，后缀原样带回去。
SUFFIXES: Tuple[str, ...] = ("s", "es", "d", "ed", "ing", "ly", "er", "ers", "ness")

# 按后缀末字母索引，查词时只试可能命中的那几个
SUFFIX_BY_LAST: Dict[str, Tuple[str, ...]] = {}
for _suffix in SUFFIXES:
    SUFFIX_BY_LAST[_suffix[-1]] = SUFFIX_BY_LAST.get(_suffix[-1], ()) + (_suffix,)

MIN_WORD_LEN = 3

# ---------------------------------------------------------------------------
# 扫描时跳过的目录与文件
# ---------------------------------------------------------------------------

SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", "dist", "build",
    "target", ".next", ".nuxt", "vendor", ".idea", ".cache", "coverage",
}

SKIP_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "Cargo.lock", "go.sum", "composer.lock", "Gemfile.lock", "uv.lock",
}

BINARY_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".tiff",
    ".pdf", ".zip", ".gz", ".bz2", ".xz", ".7z", ".rar", ".tar",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".o", ".a", ".pyc", ".class",
    ".woff", ".woff2", ".ttf", ".otf", ".eot", ".mp3", ".mp4", ".mov",
    ".avi", ".wav", ".flac", ".psd", ".ai", ".sketch", ".fig", ".db", ".sqlite",
}

MAX_FILE_BYTES = 1_500_000
MAX_LINE_LEN = 2000

# ---------------------------------------------------------------------------
# 指令
# ---------------------------------------------------------------------------
# 行内注释即可，不需要配置文件：
#   spell:ignore              忽略本行剩余部分
#   spell:ignore-next-line    忽略下一行
#   spell:ignore-file         整个文件不检查
#   spell:ignore=foo,bar      只忽略本行的这几个词

DIRECTIVE_FILE = re.compile(r"spell:ignore-file\b")
DIRECTIVE_NEXT = re.compile(r"spell:ignore-next-line\b")
DIRECTIVE_WORDS = re.compile(r"spell:ignore=([A-Za-z0-9_,\s]+)")
DIRECTIVE_LINE = re.compile(r"spell:ignore\b(?![=-])")

# 这些位置里的字母组合不是词，是标识符或地址
NOISE_RE = re.compile(
    r"[a-zA-Z][a-zA-Z0-9+.\-]*://\S+"                                        # URL
    r"|\b[\w.+-]+@[\w-]+\.[\w.]+\b"                                          # 邮箱
    r"|\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"  # UUID
    r"|\bv?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.\-]+)?\b"                          # 语义化版本
)

IDENT_RE = re.compile(r"[A-Za-z0-9_]+")
HEX_ONLY = re.compile(r"^[0-9a-fA-F]+$")
VOWELS = set("aeiouyAEIOUY")


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    path: str
    line: int
    col: int           # 1-based，指向词首
    word: str
    suggestion: str
    context: str
    span: Tuple[int, int]  # 行内 [start, end)，供 --fix 使用


@dataclass
class Stats:
    files: int = 0
    lines: int = 0
    findings: int = 0
    skipped: int = 0
    elapsed: float = 0.0


# ---------------------------------------------------------------------------
# 纯函数：拆词、判废、查词
# ---------------------------------------------------------------------------

def split_identifier(ident: str) -> List[Tuple[str, int, int]]:
    """把标识符拆成词，返回 [(词, 起始偏移, 结束偏移)]。

    处理 snake_case / camelCase / PascalCase / SCREAMING_CASE / 数字边界，
    并且不在缩写内部切开：HTMLParser -> HTML, Parser。
    """
    words: List[Tuple[str, int, int]] = []
    for chunk_start, chunk in _split_on_underscore(ident):
        for word, s, e in _split_camel(chunk):
            words.append((word, chunk_start + s, chunk_start + e))
    return words


def _split_on_underscore(ident: str) -> List[Tuple[int, str]]:
    chunks: List[Tuple[int, str]] = []
    start = 0
    for i, ch in enumerate(ident):
        if ch == "_":
            if i > start:
                chunks.append((start, ident[start:i]))
            start = i + 1
    if start < len(ident):
        chunks.append((start, ident[start:]))
    return chunks


def _split_camel(chunk: str) -> List[Tuple[str, int, int]]:
    """按大小写与数字边界切分，缩写整体保留。"""
    if not chunk:
        return []
    cuts = [0]
    for i in range(1, len(chunk)):
        prev, cur = chunk[i - 1], chunk[i]
        if prev.isdigit() != cur.isdigit():
            cuts.append(i)
        elif prev.islower() and cur.isupper():
            cuts.append(i)
        elif prev.isupper() and cur.isupper() and i + 1 < len(chunk) and chunk[i + 1].islower():
            cuts.append(i)
    cuts.append(len(chunk))
    out: List[Tuple[str, int, int]] = []
    for a, b in zip(cuts, cuts[1:]):
        piece = chunk[a:b]
        if piece:
            out.append((piece, a, b))
    return out


def is_opaque(ident: str) -> bool:
    """这个标识符是不是「不像人写的词」，直接跳过。

    这一层是误报的主要防线。哈希、base64 片段、版本串、编码串
    都有共同特征：字母数字混杂、几乎没有元音、长度异常。
    """
    n = len(ident)
    if n < MIN_WORD_LEN:
        return True
    # 纯字母是绝大多数，先走这条路，省掉数数字的开销
    if ident.isalpha():
        if n >= 24:
            return True
        return n >= 4 and not (set(ident) & VOWELS)

    if ident.isdigit():
        return True
    digits = sum(map(str.isdigit, ident))
    letters = n - digits

    # 数字占比高 —— 版本号、时间戳、哈希尾巴
    if digits / n > 0.30:
        return True
    # 纯十六进制且带数字 —— 摘要、颜色值、内存地址
    if n >= 6 and HEX_ONLY.match(ident):
        return True
    # 太长 —— 哈希或 base64 片段
    if n >= 24:
        return True
    # 单字母加一串数字
    if letters <= 1 and digits >= 2:
        return True
    return False


def case_like(source: str, target: str) -> str:
    """让 target 的大小写形状跟随 source：UPPER / Title / lower。"""
    if not source:
        return target
    if source.isupper() and len(source) > 1:
        return target.upper()
    if source[0].isupper() and source[1:].islower():
        return target[:1].upper() + target[1:]
    return target


def lookup(word: str) -> Optional[str]:
    """查词，返回整词的修正建议（小写）。查不到返回 None。

    先查整词，再按后缀剥一层查词干 —— `recieves` 剥掉 `s` 命中 `recieve`，
    修正时把后缀原样带回去，所以结果是 `receives` 而不是 `receivees`。
    """
    low = word.lower()
    if len(low) < MIN_WORD_LEN:
        return None
    if low in TYPOS:
        return TYPOS[low]
    for suffix in SUFFIX_BY_LAST.get(low[-1], ()):
        if not low.endswith(suffix):
            continue
        stem = low[: -len(suffix)]
        if len(stem) < MIN_WORD_LEN:
            continue
        if stem in TYPOS:
            # 词典里 `standar` -> `standard`，而 `standard` 本身是正确拼写。
            # 剥掉后缀 `d` 后若「修正结果正好等于原词」，说明原词就是对的。
            if TYPOS[stem] == low:
                continue
            return TYPOS[stem] + suffix
    return None


def mask_noise(line: str) -> List[Tuple[int, int]]:
    """找出不该被当作正文的片段（URL、邮箱、UUID、版本号）。"""
    return [(m.start(), m.end()) for m in NOISE_RE.finditer(line)]


def _in_spans(pos: int, spans: Sequence[Tuple[int, int]]) -> bool:
    for start, end in spans:
        if start <= pos < end:
            return True
    return False


# ---------------------------------------------------------------------------
# 检查一行 / 一段文本
# ---------------------------------------------------------------------------

def check_line(line: str, lineno: int, path: str,
               ignore_words: Sequence[str] = ()) -> List[Finding]:
    """检查单行，返回发现列表。纯函数，不碰文件系统。"""
    if len(line) > MAX_LINE_LEN:
        return []

    allowed = {w.lower() for w in ignore_words}
    if "spell:" in line:
        if DIRECTIVE_LINE.search(line) or DIRECTIVE_NEXT.search(line):
            return []
        m = DIRECTIVE_WORDS.search(line)
        if m:
            for raw in re.split(r"[,\s]+", m.group(1)):
                if raw:
                    allowed.add(raw.lower())

    # 只有出现 URL / 邮箱 / 版本号迹象时才去找需要屏蔽的片段
    noise: Sequence[Tuple[int, int]] = ()
    if "//" in line or "@" in line or ("-" in line and "." in line):
        noise = mask_noise(line)

    findings: List[Finding] = []
    for ident_match in IDENT_RE.finditer(line):
        ident = ident_match.group(0)
        if len(ident) < MIN_WORD_LEN:
            continue
        base = ident_match.start()
        if noise and _in_spans(base, noise):
            continue
        if is_opaque(ident):
            continue
        # 快路径：纯小写或纯大写的单个词，不需要拆
        if ident.isalpha() and (ident.islower() or ident.isupper()):
            words: List[Tuple[str, int, int]] = [(ident, 0, len(ident))]
        else:
            words = split_identifier(ident)
        for word, s, e in words:
            if word.isupper() and len(word) <= 3:
                # 全大写三字母以内一律当缩写或专名，不碰
                continue
            hit = lookup(word)
            if hit is None:
                continue
            if word.lower() in allowed:
                continue
            findings.append(Finding(
                path=path,
                line=lineno,
                col=base + s + 1,
                word=word,
                suggestion=case_like(word, hit),
                context=line.rstrip("\n"),
                span=(base + s, base + s + len(word)),
            ))
    return findings


def check_text(text: str, path: str = "<stdin>") -> List[Finding]:
    """检查整段文本。支持文件级与下一行级指令。"""
    if DIRECTIVE_FILE.search(text):
        return []
    findings: List[Finding] = []
    skip_next = False
    for i, line in enumerate(text.splitlines(), start=1):
        if skip_next:
            skip_next = False
            continue
        if DIRECTIVE_NEXT.search(line):
            skip_next = True
            continue
        findings.extend(check_line(line, i, path))
    return findings


# ---------------------------------------------------------------------------
# 文件遍历与读取
# ---------------------------------------------------------------------------

def iter_files(paths: Iterable[str], extra_skip: Sequence[str] = ()) -> Iterator[str]:
    """展开路径，跳过依赖目录、二进制、锁文件和明显的压缩产物。"""
    for root_path in paths:
        if os.path.isfile(root_path):
            if _is_scannable(root_path, extra_skip):
                yield root_path
            continue
        for root, dirs, files in os.walk(root_path):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
            for name in sorted(files):
                full = os.path.join(root, name)
                if _is_scannable(full, extra_skip):
                    yield full


def _is_scannable(path: str, extra_skip: Sequence[str]) -> bool:
    name = os.path.basename(path)
    if name in SKIP_FILES:
        return False
    if name.endswith((".min.js", ".min.css", ".map")):
        return False
    if os.path.splitext(name)[1].lower() in BINARY_EXT:
        return False
    for pattern in extra_skip:
        if pattern in path.replace("\\", "/"):
            return False
    try:
        if os.path.getsize(path) > MAX_FILE_BYTES:
            return False
    except OSError:
        return False
    return True


def read_text(path: str) -> Optional[str]:
    """读成文本。二进制、编码不合法、空文件都返回 None。"""
    try:
        with open(path, "rb") as fh:
            head = fh.read(8192)
            if b"\x00" in head:
                return None
            rest = fh.read()
    except OSError:
        return None
    try:
        return (head + rest).decode("utf-8")
    except UnicodeDecodeError:
        try:
            return (head + rest).decode("utf-8", errors="replace")
        except Exception:
            return None


# ---------------------------------------------------------------------------
# 修正
# ---------------------------------------------------------------------------

def fix_text(text: str, findings: Sequence[Finding]) -> str:
    """按发现列表就地修正文本。同一行多个发现从右往左替换，避免偏移错位。"""
    by_line: Dict[int, List[Finding]] = {}
    for f in findings:
        by_line.setdefault(f.line, []).append(f)

    lines = text.splitlines(keepends=True)
    for lineno, items in by_line.items():
        idx = lineno - 1
        if idx >= len(lines):
            continue
        line = lines[idx]
        for f in sorted(items, key=lambda x: x.span[0], reverse=True):
            start, end = f.span
            line = line[:start] + f.suggestion + line[end:]
        lines[idx] = line
    return "".join(lines)


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------

def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if not sys.stdout.isatty():
        return False
    if os.name == "nt" and not os.environ.get("WT_SESSION") and not os.environ.get("TERM"):
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            return False
    return True


def _display_width(text: str) -> int:
    """终端显示宽度。中文占两格，制表符按四格算，否则插入符对不上。"""
    width = 0
    for ch in text:
        if ch == "\t":
            width += 4
        elif unicodedata.east_asian_width(ch) in ("W", "F"):
            width += 2
        else:
            width += 1
    return width


class Printer:
    def __init__(self, color: bool) -> None:
        self.color = color

    def _c(self, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.color else text

    def finding(self, f: Finding) -> str:
        head = f"{f.path}:{f.line}:{f.col}"
        body = f"{self._c('31', f.word)} -> {self._c('32', f.suggestion)}"
        source = f.context.replace("\t", "    ").rstrip()
        pad = _display_width(source[: f.col - 1].replace("\t", "    "))
        caret = "^" * max(1, _display_width(f.word))
        return (
            f"{self._c('1', head)}  {body}\n"
            f"    {source}\n"
            f"    {' ' * pad}{self._c('31', caret)}"
        )


# ---------------------------------------------------------------------------
# 命令行
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="spellcode",
        description="检查源码里的拼写错误。零配置，只报有把握的。",
    )
    p.add_argument("paths", nargs="*", default=["."], help="要检查的文件或目录（默认当前目录）")
    p.add_argument("--fix", action="store_true", help="就地修正，而不是只报告")
    p.add_argument("--json", action="store_true", help="按行输出 JSON，便于接入其他工具")
    p.add_argument("--stat", action="store_true", help="只打印统计")
    p.add_argument("--quiet", action="store_true", help="不打印细节，只用退出码表示结果")
    p.add_argument("--no-color", action="store_true", help="关闭彩色输出")
    p.add_argument("--skip", action="append", default=[], metavar="SUBSTR",
                   help="跳过路径里包含该子串的文件，可重复")
    p.add_argument("--version", action="version", version=f"spellcode {VERSION}")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    paths = args.paths or ["."]
    for path in paths:
        if not os.path.exists(path):
            print(f"spellcode: 找不到路径 {path}", file=sys.stderr)
            return 1

    started = time.perf_counter()
    printer = Printer(color=not args.no_color and _supports_color())
    stats = Stats()
    all_findings: List[Finding] = []
    files_with_findings = 0
    fixed_total = 0

    for path in iter_files(paths, args.skip):
        text = read_text(path)
        if text is None:
            stats.skipped += 1
            continue
        stats.files += 1
        stats.lines += text.count("\n") + (1 if text and not text.endswith("\n") else 0)
        findings = check_text(text, path)
        if not findings:
            continue
        files_with_findings += 1
        all_findings.extend(findings)

        if args.fix:
            new_text = fix_text(text, findings)
            if new_text != text:
                with open(path, "w", encoding="utf-8", newline="") as fh:
                    fh.write(new_text)
                fixed_total += len(findings)
                if not args.quiet and not args.stat:
                    print(f"{printer._c('1', path)}  已修正 {len(findings)} 处")
                continue

        if args.json:
            for f in findings:
                print(json.dumps({
                    "path": f.path, "line": f.line, "col": f.col,
                    "word": f.word, "suggestion": f.suggestion,
                    "context": f.context,
                }, ensure_ascii=False))
        elif not args.quiet and not args.stat:
            for f in findings:
                print(printer.finding(f))

    stats.findings = len(all_findings)
    stats.elapsed = time.perf_counter() - started

    if not args.json and not args.quiet:
        _print_summary(stats, files_with_findings, fixed_total, args)

    if args.fix:
        return 0
    return 0 if stats.findings == 0 else 2


def _print_summary(stats: Stats, files_with_findings: int, fixed_total: int,
                   args: argparse.Namespace) -> None:
    if args.fix:
        print(f"\n修正 {fixed_total} 处，涉及 {files_with_findings} 个文件；"
              f"共检查 {stats.files} 个文件、{stats.lines} 行，用时 {stats.elapsed:.2f}s")
        return
    if stats.findings:
        print(f"\n{stats.findings} 处可疑拼写，分布在 {files_with_findings} 个文件；"
              f"共检查 {stats.files} 个文件、{stats.lines} 行，用时 {stats.elapsed:.2f}s")
        print("确认无误的可以加一行注释 spell:ignore 跳过。")
    else:
        print(f"没有发现问题：检查 {stats.files} 个文件、{stats.lines} 行，用时 {stats.elapsed:.2f}s")


if __name__ == "__main__":
    sys.exit(main())
