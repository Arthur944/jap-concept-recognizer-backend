import json

from rest_framework.response import Response
from rest_framework import permissions, status
from rest_framework.views import APIView
from kuromojipy.kuromoji_server import KuromojiServer
kuro_server = KuromojiServer()
from jap_concept_recognizer.logic.japanese_text_extractor.japanese_text_extractor import extract_japanese_text
from jap_concept_recognizer.logic.grammar_recognizer import encode_tags
from jap_concept_recognizer.logic.concept_mapper import *
import romkan


class TestView(APIView):
    def post(self, request, format=None):
        data = json.loads(request.body)
        sent = data["sent"]
        id_reference = data["idRef"]
        if id_reference is None:
            id_reference = open("jap_concept_recognizer/logic/id_reference.csv", "r").read()
        mapper = ConceptMapper(kuro_server, id_reference, "293", "490")
        results = []
        jap_texts = extract_japanese_text(sent)
        analyzed_sents = [mapper.analyze_sent(x) for x in jap_texts]
        concepts = []
        for i in range(len(analyzed_sents)):
            try:
                concepts += [x.id for x in analyzed_sents[i]["found_grammars"] + analyzed_sents[i]["found_words"]] + analyzed_sents[i]["kana"]
            except:
                print(analyzed_sents)
            analyzed_sents[i]["found_grammars"] = [str(x) for x in analyzed_sents[i]["found_grammars"]]
            analyzed_sents[i]["found_words"] = [str(x) for x in analyzed_sents[i]["found_words"]]
            analyzed_sents[i]["text"] = jap_texts[i]
            analyzed_sents[i]["sent"] = jap_texts[i]
            results.append(analyzed_sents[i])
        return Response({"analyzed_sents": results, "concepts": list(set(concepts))}, status=status.HTTP_200_OK)
