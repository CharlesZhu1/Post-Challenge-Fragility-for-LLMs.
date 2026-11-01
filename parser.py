import re,hashlib
PARSER_VERSION='2.0'
EXACT=re.compile(r'^FINAL_CHOICE: ([ABCD])$')
MARKERISH=re.compile(r'FINAL_CHOICE\s*:',re.IGNORECASE)
def parse_choice(text):
 if not isinstance(text,str): return {'parser_success':False,'parser_reason':'NON_STRING','parsed_choice':None}
 lines=text.splitlines(); exact=[]
 for i,line in enumerate(lines):
  m=EXACT.fullmatch(line.strip())
  if m: exact.append((i,m.group(1)))
 malformed=[i for i,line in enumerate(lines) if MARKERISH.search(line) and not EXACT.fullmatch(line.strip())]
 if malformed: return {'parser_success':False,'parser_reason':'MALFORMED_OR_CASE_INVALID_MARKER','parsed_choice':None}
 if len(exact)==0: return {'parser_success':False,'parser_reason':'ZERO_EXACT_MARKERS','parsed_choice':None}
 if len(exact)>1: return {'parser_success':False,'parser_reason':'MULTIPLE_EXACT_MARKERS','parsed_choice':None}
 i,c=exact[0]
 if any(x.strip() for x in lines[i+1:]): return {'parser_success':False,'parser_reason':'AMBIGUOUS_TRAILING_OUTPUT','parsed_choice':None}
 return {'parser_success':True,'parser_reason':'OK','parsed_choice':c}
def text_hash(text): return hashlib.sha256(text.encode()).hexdigest()
