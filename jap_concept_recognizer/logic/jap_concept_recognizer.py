import re
from jap_concept_recognizer.logic.grammar_recognizer import recognize_grammar as real_recognize_grammar, pos_tag as real_pos_tag, encode_tags
from jap_concept_recognizer.logic.consts import pos_tag_translations, pos_tag_encodings, grammars, kanji_id, word_id
from jap_concept_recognizer.logic.sents import *
from kuromojipy.kuromoji_server import KuromojiServer
import romkan
from functools import reduce
from jap_concept_recognizer.logic.japanese_text_extractor.japanese_text_extractor import clean_html
kuro_server = KuromojiServer()


def pos_tag(sent):
    return real_pos_tag(sent, kuro_server)


def recognize_grammar(sent):
    return real_recognize_grammar(sent, kuro_server)


id_reference = [[y.strip() for y in x.split(";")] for x in open("../id_reference.csv", "r").readlines()]


class Concept:
    def __init__(self, id, parent_id, name):
        self.id = id
        self.name = name
        self.parent_id = parent_id

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name


id_index = {x[0]: Concept(*x) for x in id_reference[1:]}
name_index = {x[2]: Concept(*x) for x in id_reference[1:]}


def fill_collection_dic(dic, parent_id):
    for key in id_index.keys():
        concept = id_index[key]
        if concept.parent_id == parent_id and concept.name != "Primitives":
            print(concept.name)
            match = re.search("from (.+) produce (.+)", concept.name)
            if not re.search("[A-Za-z]+", match.group(1)):
                symbol, meaning = match.group(1), match.group(2)
                if symbol not in dic:
                    dic[symbol] = {"read": None, "produce": None}
                dic[symbol]["read"] = concept
            else:
                meaning, symbol = match.group(1), match.group(2)
                if symbol not in dic:
                    dic[symbol] = {"read": None, "produce": None}
                dic[symbol]["produce"] = concept
    return dic


kanji_index = fill_collection_dic({}, kanji_id)
word_index = fill_collection_dic({}, word_id)
grammar_index = {x: id_index[str(grammars[x])] for x in grammars.keys()}


def words_in_sent(sent):
    stems = [x[0] for x in pos_tag(sent)]
    words = []
    for stem in stems:
        if stem in word_index.keys():
            words.append({"word": stem})
    return words


def sent_prereqs(sent):
    grammars = recognize_grammar(sent)
    words = [x['read'] for x in words_in_sent(sent)]
    return grammars + words


def word_coords_in_encoded(word, pos_tags, encoded):
    hits = []
    for i in range(len(pos_tags)):
        if pos_tags[i][0] == word["word"]:
            hits.append({"index": i, "word": word["word"]})
    coords = []
    for hit in hits:
        match = re.search("(ő[^ú]+ú){" + str(hit["index"]) + "}(ő[^ú]+ú)", encoded)
        coords.append([match.start(2), match.end(2)])
    return {"word": word_index[word["word"]], "coords": coords}


def find_word_index_in_encoded(char_index, encoded):
    return len(re.findall("ő[^ú]+ú", encoded[:char_index + 1]))


def is_missing_word_bad(pos_tag):
    if 'number' in pos_tag[1]:
        return False
    return True


def analyze_sent(sent):
    pos_tags = list(filter(lambda x: "symbol" not in x[1], pos_tag(sent)))
    encoded = encode_tags(pos_tags)
    found_words = words_in_sent(sent)
    grammars = recognize_grammar(sent)
    word_coords = reduce(lambda x, y: x + [y], [word_coords_in_encoded(z, pos_tags, encoded) for z in found_words], [])
    coords = [x["coords"] for x in word_coords] + [[[x["start"], x["end"]]] for x in grammars if
                                                   x["name"] in grammar_index]
    real_coords = []
    for cord_container in coords:
        real_coords += cord_container
    missing_intervals = calc_missing_intervals(real_coords + [[len(encoded), len(encoded)]])
    missing_words = [pos_tags[find_word_index_in_encoded(x[0], encoded)] for x in missing_intervals]
    missing_words = list(filter(lambda x: is_missing_word_bad(x), missing_words))
    if not missing_words:
        return [found_words + grammars, True]
    else:
        return [missing_words, False]


def calc_missing_intervals(coords):
    length = max(coords, key=lambda x: x[1])[1]
    section = [0] * length
    for coord in coords:
        section[coord[0]:coord[1]] = [1] * (coord[1] - coord[0])
    missing = []
    last_good = 0
    for i in range(len(section)):
        if section[i] == 1 and last_good < i - 1:
            missing.append([last_good + 1, i - 1])
        if section[i] == 1:
            last_good = i
    if last_good < len(section) - 1:
        missing.append([last_good + 1, len(section) - 1])
    return missing


def calc_max_ok_index(coords):
    intervals = reduce(lambda x, y: x + y, [x for x in coords])
    intervals = list(sorted(intervals, key=lambda x: x[0]))
    max_index = 0
    for i in range(len(intervals)):
        if intervals[i][0] <= max_index + 1:
            max_index = intervals[i][1]
        else:
            return max_index
    return max_index


def is_sent_ok(sent):
    result = analyze_sent(sent)
    if not result[1]:
        print(result)
    return result[1]


def n_of_good_sents(sents):
    all_sents = len(sents)
    good_sents = len(list(filter(lambda x: is_sent_ok(x), sents)))
    return good_sents/all_sents


def concepts_to_dic(dic):
    return_list = []
    if 'word' in dic.keys():
        return_list.append(word_index[dic['word']]['read'])
    if 'name' in dic.keys() and dic['name'] in grammar_index.keys():
        return_list.append(grammar_index[dic['name']])
    return return_list


def concepts_from_sent(sent):
    result = analyze_sent(sent)
    if result[1]:
        return reduce(lambda x, y: x + y, [concepts_to_dic(x) for x in result[0]])
