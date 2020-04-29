from django.test import TestCase
from jap_concept_recognizer.logic.concept_mapper import ConceptMapper
from kuromojipy.kuromoji_server import KuromojiServer

from jap_concept_recognizer.logic.grammar_recognizer import recognize_grammar, encode_tags

kuro_server = KuromojiServer()
import pprint
pp = pprint.PrettyPrinter(indent=4)


class TestGrammarRecognizer(TestCase):
    def setUp(self):
        id_reference = open("jap_concept_recognizer/logic/id_reference.csv", "r").read()
        self.mapper = ConceptMapper(kuro_server, id_reference, "293", "490")

    def test_mapper(self):
        sent = "部屋に田中さんがいる"
        pos_tags = self.mapper.pos_tag(sent)
        encoded = encode_tags(pos_tags)
        analyzed = self.mapper.analyze_sent(sent)
        pp.pprint(analyzed)


# Create your tests here.
