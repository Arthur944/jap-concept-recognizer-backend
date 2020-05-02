import re
import jap_concept_recognizer.logic.grammar_recognizer as gr
import importlib
from jap_concept_recognizer.logic.grammar_recognizer import recognize_grammar, pos_tag, encode_tags
from jap_concept_recognizer.logic.consts import pos_tag_translations, pos_tag_encodings, grammars, hiragana_matrix, \
    e_hiragana, find_matrix_index, all_katakana
from jap_concept_recognizer.logic.sents import *
import romkan
from functools import reduce
from jap_concept_recognizer.logic.japanese_text_extractor.japanese_text_extractor import extract_japanese_text
from .kana_mapper import KanaMapper


class Concept:
    def __init__(self, id, parent_id, name):
        self.id = id
        self.name = name
        self.parent_id = parent_id

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name


class WordConcept:
    def __init__(self, read, produce, stem):
        self.read = read
        self.produce = produce
        self.stem = stem

    def __str__(self):
        return self.stem

    def __repr__(self):
        return self.__str__()


class ConceptMapper:
    def __init__(self, server, id_reference, kanji_id, word_id):
        self.word_id = word_id
        self.kanji_id = kanji_id
        self.server = server
        self.kana_mapper = KanaMapper(id_reference)
        id_reference = [[y.strip() for y in x.split(";")] for x in id_reference.splitlines()]
        self.id_index = {x[0]: Concept(*x) for x in id_reference[1:]}
        self.name_index = {x[2]: Concept(*x) for x in id_reference[1:]}
        self.grammar_index = {x: (self.id_index[str(grammars[x])]) for x in grammars.keys()}
        self.kanji_index = {x.name: x for x in self.id_index.values() if x.parent_id == kanji_id}
        self.word_index = {x.name: x for x in self.id_index.values() if x.parent_id == word_id}
        self.word_index["この"] = [self.word_index["これ"], self.grammar_index["the の particle"]]
        self.word_index["あの"] = [self.word_index["あれ"], self.grammar_index["the の particle"]]
        self.word_index["その"] = [self.word_index["それ"], self.grammar_index["the の particle"]]
        self.word_index['そこで'] = [self.word_index['そこ'], self.grammar_index['The contextual で particle']]
        self.setup_exception_words()
        self.pos_tags = None
        self.encoded = None

    def setup_exception_words(self):
        exceptions = [
            ('いる', "居る"),
            ('ある', '有る'),
            ('けっして', '決して'),
            ('こと', '事'),
            ('そんな', 'そんなに'),
            ('くる', '来る'),
            ('できる', '出来る'),
            ('いい', '良い'),
            ('よい', '良い'),
            ('もの', '物'),
            ('みる', '見る'),
            ('いく', '行く'),
            ('とき', '時'),
            ('ほど', '程'),
            ('すぐ', '直ぐ'),
            ('わかる', '分かる'),
            ('とる', '取る'),
            ('子ども', '子供'),
            ('やすい', '安い'),
            ('すべて', '全て'),
        ]
        for elem in exceptions:
            self.word_index[elem[0]] = self.word_index[elem[1]]

    def pos_tag(self, sent):
        return pos_tag(sent, self.server)

    def recognize_grammar(self, sent, pos_tags=None, encoded=None):
        if pos_tags is None:
            pos_tags = self.pos_tags
        if encoded is None:
            encoded = self.encoded
        if pos_tags and encoded:
            return [{
                **x,
                "coords": [{
                    "start": encoded_index_to_pos_index(y["start"], encoded),
                    "end": encoded_index_to_pos_index(y["end"], encoded) if encoded_index_to_pos_index(y['end'],
                                                                                                       encoded) != 0 else 0,
                    "abs_pos": [encoded_index_to_abs_index(y["start"], encoded, pos_tags)[0],
                                encoded_index_to_abs_index(y['end'] - 1, encoded, pos_tags)[1]],
                } for y in x["coords"]]
            } for x in recognize_grammar(sent, self.server)]

    def analyze_sent(self, sent):
        pos_tags = self.pos_tag(sent)
        self.pos_tags = pos_tags
        self.encoded = encode_tags(pos_tags)
        found_words, grammar_in_words = self.find_words_in_sent(pos_tags)

        found_grammars = self.recognize_grammar(sent)
        grammar_coords = []
        for grammar in found_grammars:
            for coord in grammar["coords"]:
                grammar_coords.append([coord["start"], coord["end"]])
        coords = [x["coords"] for x in found_words] + grammar_coords
        missing_tags = calc_missing_tags(coords + [[len(pos_tags) - 1, len(pos_tags)]])
        kana = self.kana_mapper.word_prereqs(sent)
        to_return = {
            "found_words": [self.word_index[x["stem"]] for x in found_words],
            "found_grammars": [self.grammar_index[x["name"]] for x in found_grammars if
                               x["name"] in self.grammar_index] + grammar_in_words,
            "missing": self.filter_real_missing(missing_tags, pos_tags),
            "verbose_found_words": [
                [
                    x['stem'],
                    [pos_index_to_abs_index(y, pos_tags) for y in x['coords']][0],
                    x["surface_form"],
                    pos_tags,
                ]
                for x in found_words],
            "verbose_found_grammars": [[x["name"], x["coords"]] for x in found_grammars] + [
                [x.name, [{"start": 0, "end": 0, "abs_pos": [0, 0]}]] for x in grammar_in_words],
            "pos_tags": pos_tags,
            "kana": kana
        }
        return to_return

    def filter_real_missing(self, missing_tags, pos_tags):
        tags = reduce(lambda acc, curr_value: acc + [pos_tags[curr_value]], missing_tags, [])
        tags = [x for x in tags if "number" not in x[1] and "symbol" not in x[1] and set(x[0]).difference(set(all_katakana)) != set() and x[0] not in ["さん"]]
        return tags

    def find_words_in_sent(self, pos_tags):
        stems = [x[0] for x in pos_tags]
        surface_forms = [x[2] for x in pos_tags]
        indexes = [(x, x + 1) for x in range(len(pos_tags))]
        for i in range(1, len(pos_tags)):
            stems.append(pos_tags[i - 1][0] + pos_tags[i][0])
            surface_forms.append(pos_tags[i - 1][2] + pos_tags[i][2])
            indexes.append((i - 1, i + 1))
            if i >= 2:
                stems.append(pos_tags[i - 2][0] + pos_tags[i - 1][0] + pos_tags[i][0])
                surface_forms.append(pos_tags[i - 2][2] + pos_tags[i - 1][2] + pos_tags[i][2])
                indexes.append((i - 2, i + 1))

        def add_word(stem, index):
            if type(self.word_index[stem]) == list:
                for elem in self.word_index[stem]:
                    if elem.parent_id != self.word_id:
                        grammar_in_words.append(elem)
                    else:
                        words.append({"stem": elem.name, "coords": indexes[index], "surface_form": surface_forms[index]})
            else:
                words.append({"stem": stem, "coords": indexes[index], "surface_form": surface_forms[index]})

        words = []
        grammar_in_words = []
        for i in range(len(stems)):
            if stems[i] in self.word_index.keys():
                if stems[i] == "から" and "conjunction particle" in pos_tags[i][1]:
                    continue
                add_word(stems[i], i)
            else:
                """Potential form is not correctly stemmed by the pos tagger."""
                if surface_forms[i][-1] in e_hiragana:
                    row_index, col_index = find_matrix_index(surface_forms[i][-1], hiragana_matrix)
                    real_stem = surface_forms[i][:-1] + hiragana_matrix[row_index][4]
                    if real_stem in self.word_index.keys():
                        add_word(real_stem, i)
                        grammar_in_words.append(self.grammar_index['potential form'])
        return words, grammar_in_words

    def fill_collection_dic(self, dic, parent_id):
        for key in self.id_index.keys():
            concept = self.id_index[key]
            if concept.parent_id == parent_id and concept.name != "Primitives":
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


def calc_missing_tags(coords):
    length = max(coords, key=lambda x: x[1])[1]
    section = [0] * length
    for coord in coords:
        if coord[1] != coord[0]:
            section[coord[0]:coord[1]] = [1] * (coord[1] - coord[0])
    missing = []
    for i in range(0, len(section)):
        if section[i] == 0:
            missing.append(i)
    return missing


def encoded_index_to_pos_index(encoded_index, encoded):
    text = encoded[:encoded_index]
    return text.count("ú")


def pos_index_to_abs_index(pos_index, pos_tags):
    start_index = 0
    for pos_tag in pos_tags[:pos_index]:
        start_index += len(pos_tag[2])
    if len(pos_tags) > pos_index:
        return [start_index, start_index + len(pos_tags[pos_index][2])]
    else:
        return [start_index, start_index]


def encoded_index_to_abs_index(encoded_index, encoded, pos_tags):
    pos_index = encoded_index_to_pos_index(encoded_index, encoded)
    return pos_index_to_abs_index(pos_index, pos_tags)
