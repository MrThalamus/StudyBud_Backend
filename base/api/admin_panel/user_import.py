import codecs
import csv
import io
from dataclasses import dataclass

ALLOWED_EXTENSIONS = ('.txt',) 
MAX_FILE_SIZE = 1 * 1024 * 1024
MAX_ROWS = 500
REQUIRED_COLUMNS = ('email', 'username', 'name', 'password')
OPTIONAL_COLUMNS = ('bio',)
DELIMITER = ','                 

FIELDS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS   
NOT_STRIPPED = ('password',)               
class ImportFileError(Exception):
  

  @dataclass
  class Row:
    line: int          # line number in the file, as the admin sees it in the editor
    data: dict         # only FIELDS, cleaned, ready for the serializer
    problem: str = ''  # set when the row's shape is wrong; such a row is reported, not saved

def check_upload(upload):
  if not upload.name.lower().endswith(ALLOWED_EXTENSIONS):
    allowed = ' or '.join(ALLOWED_EXTENSIONS)
    raise ImportFileError(f'Only {allowed} files are allowed.')
  if upload.size == 0:
    raise ImportFileError('The file is empty.')
  if upload.size > MAX_FILE_SIZE:
    raise ImportFileError(f'File is too large (max {MAX_FILE_SIZE // (1024 * 1024)} MB).')


def decode(raw):
  """bytes -> str. Supports UTF-8 (with or without BOM) and UTF-16 with BOM."""
  if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
    encoding = 'utf-16'        # reads the BOM, picks the byte order, removes the BOM
  else:
    encoding = 'utf-8-sig'     # removes the UTF-8 BOM if present
  try:
    return raw.decode(encoding)
  except UnicodeDecodeError:
    raise ImportFileError('File must be saved as UTF-8 or UTF-16 text.') from None


def read_header(text):
  first_line = (text.splitlines() or [''])[0]   # handles \n, \r\n and \r line endings
  if not first_line.strip():
    raise ImportFileError(f'Line 1 must be the header: {", ".join(REQUIRED_COLUMNS)}.')

  try:
    cells = next(csv.reader([first_line], delimiter=DELIMITER))
  except csv.Error:
    raise ImportFileError('Line 1 (the header) could not be read.') from None
  columns = [cell.strip().lower() for cell in cells]

  missing = [c for c in REQUIRED_COLUMNS if c not in columns]
  if missing:
    raise ImportFileError(f'Missing columns: {", ".join(missing)}. '
                          'Columns must be separated by commas.')

  duplicates = sorted({c for c in columns if c and columns.count(c) > 1})
  if duplicates:
    raise ImportFileError(f'Duplicate columns: {", ".join(duplicates)}.')

  return columns

def read_rows(text, columns):
  reader = csv.reader(io.StringIO(text, newline=''), delimiter=DELIMITER)
  rows = []

  try:
    next(reader)  
    for cells in reader:
      if not any(cell.strip() for cell in cells):
        continue   # blank line or only separators

      if len(rows) >= MAX_ROWS:
        raise ImportFileError(f'Too many rows (max {MAX_ROWS}).')

      problem = ''
      extra = cells[len(columns):]
      if any(cell.strip() for cell in extra):
        problem = (f'This line has {len(cells)} values but the header has {len(columns)} columns. ' 'If a value contains a comma, put it in double quotes.')

      values = dict(zip(columns, cells))
      data = {}
      for field in FIELDS:
        value = values.get(field, '')
        data[field] = value if field in NOT_STRIPPED else value.strip()

      rows.append(Row(line=reader.line_num, data=data, problem=problem))
  except csv.Error as e:
    raise ImportFileError(f'Line {reader.line_num} could not be read: {e}') from None

  if not rows:
    raise ImportFileError('The file has no user rows.')
  return rows


def parse_upload(upload):
  check_upload(upload)
  text = decode(upload.read())
  columns = read_header(text)
  return read_rows(text, columns)