import re

def clean_html(text):
    return re.sub("<[^>]+?>", "", text)

def extract_japanese_text(text):
    pattern = "[^a-zA-z0-9, .?\n&;\-:)(：。「」/？！!”）（→]{2,}"
    matches = re.finditer(pattern, clean_html(text))
    sents = []
    for match in matches:
        sents.append(match.group())
    return sents