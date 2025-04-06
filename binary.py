import argparse
import codecs
import math

# import pdb
import re
from pathlib import Path

import Decorator as D
import Utility as U

NoBreakSpace = "\u00a0"  # chr(int("0xA0", 16))
ReplacementCharacter = "\ufffd"  # chr(int("0xFFFD", 16))  # �


def printHexList(l):
  print(len(l))
  print([f"{x:02X}" for x in l])


class Binary:
  Separator = " | "
  SeparatorNoBreakSpace = " |" + NoBreakSpace  # 結合させない為にNoBreakSpaceにする
  ReplacementCode = " " * 6
  Replacement = "__"

  def __init__(self, inputPath, outputPath, encoding="utf-8", outputLength=16, replChar=" ", *, outputVertical=False):
    self.inputPath = Path(inputPath)
    self.outputPath = Path(outputPath)
    self.encoding = encoding
    self.outputLength = outputLength  # 表示幅 Byte
    self.errorPosition = set()

    self.rawData = b""  # バイナリデータ
    self.lineNumber = -1  # バイナリデータを表示するのに必要な行数
    self.size = -1
    self.offsetTemplate = ""
    self.string = []  # 文字データ
    self.codePoint = []  # Unicode code point
    self.replChar = replChar  # デコード出来ない場合に置き換える文字
    self.outputVertical = outputVertical  # 垂直方向に並べて出力するかどうか

    codecs.register_error("customReplace", self.customErrorHandler)
    self.checkEncoding()

  # encode/decode時にエラーが発生した場合、その場所を記録する
  def customErrorHandler(self, e):
    self.errorPosition.update(range(e.start, e.end))
    return ((e.end - e.start) * self.replChar, e.end)

  # Bomが付くと動作がおかしくなるので変更する
  def checkEncoding(self):
    utf16 = re.compile("utf[ _-]?16$", re.IGNORECASE)
    if utf16.match(self.encoding) is not None:
      self.encoding = "utf_16le"
    utf32 = re.compile("utf[ _-]?32$", re.IGNORECASE)
    if utf32.match(self.encoding) is not None:
      self.encoding = "utf_32le"
    print(f"Encoding = {self.encoding}")

  # データをメモリに読み込むが、処理に必要なだけ読み込むようにした方が良いかも
  @D.printStartEndExecuteTime
  def read(self):
    with self.inputPath.open("rb") as file:
      self.rawData = file.read()
    self.size = len(self.rawData)
    self.lineNumber = math.ceil(self.size / self.outputLength)
    offsetLength = len(f"{self.size:X}")
    self.offsetTemplate = f"{{:{offsetLength}X}}{{:2}}{Binary.Separator}"

  def getRawData(self, line):
    start = self.outputLength * line
    end = start + self.outputLength
    return self.rawData[start:end]

  # Bom付きのencodingの場合、バイト数が正しく取得できない
  def getEncodeLength(self, data):
    l = len(data.encode(self.encoding, errors="ignore"))  # decodeが成功したものをencodeするのでignoreで良い
    return l if l > 0 else 1

  # encodeした結果、3batesならば"あ____"のような文字列を作成する
  def getCharacter(self, c, length):
    string = [U.replaceControl(c, self.Replacement)]
    string += [self.Replacement for _ in range(length - 1)]
    return string

  def getCodePoint(self, c, length):
    code = [f"{ord(c):<6X}"]
    code += [self.ReplacementCode for _ in range(length - 1)]
    return code

  @D.printStartEndExecuteTime
  def getData(self, s):
    string = []
    code = []
    i = 0
    length = 0
    for c in s:
      if i in self.errorPosition:  # decode出来なかった文字の場合、そこを別の文字で置き換える
        string += [self.replChar]
        code += [self.ReplacementCode]
        i += 1
      else:
        length = self.getEncodeLength(c)
        string += self.getCharacter(c, length)
        code += self.getCodePoint(c, length)
        i += length
    return string, code

  # 1列のデータを行毎に折り返す。
  @D.printStartEndExecuteTime
  def wrapData(self, data):
    ret = []
    for i in range(self.lineNumber):
      start = i * self.outputLength
      end = start + self.outputLength
      ret.append(data[start:end])
    return ret

  @D.printStartEndExecuteTime
  def getString(self):
    string = self.rawData.decode(self.encoding, errors="customReplace")
    s, c = self.getData(string)
    self.string = self.wrapData(s)
    self.codePoint = self.wrapData(c)

  @D.printStartEndExecuteTime
  def getTitleHorizontal(self, *, outputString=True, outputCodePoint=True):
    offset = len(self.getOffset(0)) * " "
    addList = [f"{i:02X}" for i in range(self.outputLength)]
    address = " ".join(addList)
    ret = offset + address
    if outputCodePoint:
      ret += Binary.Separator + "     ".join(addList) + "    "
    if outputString:
      ret += Binary.Separator + address
    ret += "\n\n"
    return ret

  @D.printStartEndExecuteTime
  def getTitleVertical(self, *, outputCodePoint=True):
    offset = len(self.getOffset(0)) * " "
    addList = [f"{i:02X}" for i in range(self.outputLength)]
    address = " ".join(addList)
    ret = offset + address
    if outputCodePoint:
      ret = offset + "     ".join(addList) + "    "
    ret += "\n\n"
    return ret

  def getOffset(self, line, t=""):
    return self.offsetTemplate.format(line, t)

  def getRawString(self, line, *, fill=True):
    string = self.getRawData(line).hex().upper()
    if fill and len(string) < self.outputLength * 2:
      string += " " * (self.outputLength * 2 - len(string))
    return string

  def outputStringLine(self, line, *, vertical=False):
    string = ""
    sep = NoBreakSpace
    if vertical:
      sep = NoBreakSpace * 5
    for s in self.string[line]:
      string += s + sep
      if s != self.Replacement and U.getEaWidth(s) == 1:
        string += NoBreakSpace
    return string

  def outputCodePointLine(self, line, *, fill=True):
    if not fill or line != self.lineNumber - 1:
      return " ".join(self.codePoint[line])
    diff = self.outputLength - len(self.codePoint[line])
    tail = " " * 7 * diff
    return " ".join(self.codePoint[line]) + tail

  def outputLineHorizontal(self, line, *, outputString=True, outputCodePoint=True):
    offset = self.getOffset(line * self.outputLength)
    rawString = self.getRawString(line)
    output = offset + U.insertSeparator(rawString, 2, " ")
    if outputCodePoint:
      output += Binary.Separator
      output += self.outputCodePointLine(line)
    if outputString:
      output += Binary.SeparatorNoBreakSpace
      output += self.outputStringLine(line)
    output += "\n"
    return output

  def outputLineVertical(self, line, *, outputString=True, outputCodePoint=True):
    offsetR = self.getOffset(line * self.outputLength, " B")
    rawString = self.getRawString(line, fill=False)
    output = offsetR + U.insertSeparator(rawString, 2, " " * 5) + "\n"
    if outputCodePoint:
      offsetC = self.getOffset(line * self.outputLength, " C")
      output += offsetC + self.outputCodePointLine(line, fill=False) + "\n"
    if outputString:
      offsetD = self.getOffset(line * self.outputLength, " S")
      output += offsetD + self.outputStringLine(line, vertical=True) + "\n"
    output += "\n"
    return output

  def writeHorizontal(self, file):
    file.write(self.getTitleHorizontal())
    for i in range(self.lineNumber):
      file.write(self.outputLineHorizontal(i))

  def writeVertical(self, file):
    file.write(self.getTitleVertical())
    for i in range(self.lineNumber):
      file.write(self.outputLineVertical(i))

  @D.printStartEndExecuteTime
  def write(self):
    with self.outputPath.open("w", encoding="utf-8") as file:
      if self.outputVertical:
        self.writeVertical(file)
      else:
        self.writeHorizontal(file)

  def perform(self):
    self.read()
    self.getString()
    # U.printList(self.string)
    # U.printList(self.codePoint)
    # printHexList(self.errorPosition)
    self.write()


def argumentParser():
  parser = argparse.ArgumentParser()
  parser.add_argument("inputPath", help="input path")
  parser.add_argument("-o", "--outputPath", default="output.txt", help="output path")
  parser.add_argument("-e", "--encoding", default="utf-8", help="encodeing")
  parser.add_argument("-l", "--length", type=int, default=16, help="length")
  parser.add_argument("-v", "--outputVertical", action="store_true", help="output vertical")
  parser.add_argument("-a", "--showArgument", action="store_true", help="show arguments.")
  return parser.parse_args()


if __name__ == "__main__":
  args = argumentParser()
  if args.showArgument:
    print(args)

  binary = Binary(
    inputPath=args.inputPath,
    outputPath=args.outputPath,
    encoding=args.encoding,
    outputLength=args.length,
    outputVertical=args.outputVertical,
  )
  binary.perform()
