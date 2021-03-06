from django.contrib.admin.utils import flatten

from jap_concept_recognizer.logic.consts import pos_tag_translations, pos_tag_encodings
import re
import romkan

ru_verb_exceptions = [x.strip() for x in open("jap_concept_recognizer/logic/ru-verb-exceptions.txt", "r").readlines()]


def ru_or_u_verb(pos_tags):
    if 'verb' in pos_tags[1]:
        if pos_tags[0] in ["する", "くる"]:
            return "exception"
        if pos_tags[0][-1] != "る":
            return 'u-verb'
        roma = romkan.to_roma(pos_tags[0].replace(pos_tags[2], pos_tags[3]))
        if roma[-3] not in ['i', 'e']:
            return 'u-verb'
        else:
            if pos_tags[0] not in ru_verb_exceptions:
                return 'ru-verb'
            else:
                return 'u-verb'


def encode_tags(tags):
    tag_encodings = pos_tag_encodings
    encoded = ""
    for tag in tags:
        encoded += "".join([
            "ő",
            tag[0],
            ";",
            ",".join([str(y) for y in list(sorted([tag_encodings[x] for x in tag[1]]))]),
            ";",
            tag[2],
            ";",
            tag[3],
            "ú"
        ])
    return encoded


def pos_interpreter(pos):
    translations = pos_tag_translations
    tags = pos.split(',')
    real_tags = []
    for tag in tags:
        if tag != "*":
            if tag in translations.keys():
                real_tags.append(translations[tag])
            else:
                pass
                # print(tag)
    return real_tags


def pos_tag(sentence, kuro_server):
    tagged_words = []
    kuromoji = kuro_server.kuromoji
    tokenizer = kuromoji.Tokenizer.builder().build()
    tokens = tokenizer.tokenize(sentence)
    for elem in [[
        x.getBaseForm() if x.getBaseForm() is not None else x.getSurfaceForm(),
        pos_interpreter(x.getPartOfSpeech()),
        x.getSurfaceForm(),
        x.getReading(),
    ] for x in tokens]:
        ru_or_u = ru_or_u_verb(elem)
        if ru_or_u:
            tagged_words.append(
                [elem[0], [*elem[1], ru_or_u], elem[2], romkan.to_roma(elem[0]), elem[3], romkan.to_roma(elem[3])])
        else:
            try:
                tagged_words.append([elem[0], elem[1], elem[2], romkan.to_roma(elem[0]) if elem[0] else "", elem[3],
                                     romkan.to_roma(elem[3])])
            except:
                pass
    return tagged_words


def create_word_pattern(surface_form=None, base_form=None, tags=None, romaji=None):
    if surface_form is None:
        surface_form = "[^ú]+?"
    if base_form is None:
        base_form = "[^;]+?"
    if romaji is None:
        romaji = "[^ú]*"
    if tags is None:
        tags = "[0-9,]*"
    else:
        req_tags = list(tags)
        tags = ""
        for tag in req_tags:
            tags += "([0-9]+,)*?" + str(tag) + ",?"
    return "ő" + base_form + ";" + tags + "[0-9,]*" + ";" + surface_form + ";" + romaji + "ú"


def recognize_pattern(encoded, pattern, name, before_pattern=None):
    matches = re.finditer(pattern, encoded)
    coords = []
    for match in matches:
        if before_pattern is not None:
            before_pattern_matches = re.finditer(before_pattern, encoded[:match.start()])
            ends = [x.end() for x in before_pattern_matches]
            if ends:
                biggest_index = max(ends)
                if biggest_index != match.start():
                    continue
            else:
                continue
        coords.append({"start": match.start(), "end": match.end()})
    if coords:
        return {"name": name, "coords": coords}


def recognize_da(encoded):
    pattern = create_word_pattern(base_form="だ", surface_form="(だ|だっ)", tags=[7])
    return recognize_pattern(encoded, pattern, "declaring using だ")


def recognize_negative_state_of_being(encoded):
    pattern = \
        create_word_pattern(base_form="じゃ", surface_form="じゃ", tags=[3, 15]) + \
        create_word_pattern(base_form="ない", surface_form="ない", tags=[7])
    return recognize_pattern(encoded, pattern, "Negative state of being")


def recognize_past_negative(encoded):
    before_pattern = create_word_pattern(tags=[1])
    pattern = \
        create_word_pattern(base_form="じゃ", surface_form="じゃ", tags=[3, 15]) + \
        create_word_pattern(base_form="ない", surface_form="なかっ", tags=[7]) + \
        create_word_pattern(base_form="た", surface_form="た", tags=[7])
    return recognize_pattern(encoded, pattern, "Past negative", before_pattern)


def recognize_past_state_of_being(encoded):
    pattern = \
        create_word_pattern(base_form="だ", surface_form="だっ", tags=[7]) + \
        create_word_pattern(base_form="た", surface_form="た", tags=[7])
    return recognize_pattern(encoded, pattern, "Past state of being")


def recognize_topic_particle(encoded):
    pattern = \
        create_word_pattern(base_form="は", surface_form="は", tags=[3, 11])
    return recognize_pattern(encoded, pattern, "The は topic particle")


def recognize_inclusive_particle(encoded):
    pattern = \
        create_word_pattern(base_form="も", surface_form="も", tags=[3, 11])
    return recognize_pattern(encoded, pattern, "The も inclusive topic particle")


def recognize_identifier_particle(encoded):
    pattern = \
        create_word_pattern(base_form="が", surface_form="が", tags=[2, 3, 4])
    return recognize_pattern(encoded, pattern, "The が identifier particle")


def recognize_na_adj(encoded):
    pattern = \
        create_word_pattern(tags=[1, 16])
    result = recognize_pattern(encoded, pattern, "na-adjectives")
    if result:
        return {**result, "coords": [{"start": 0, "end": 0}]}


def recognize_na_conj(encoded):
    before_pattern = create_word_pattern(tags=[1, 16])
    pattern = \
        create_word_pattern(surface_form="じゃ") + \
        create_word_pattern(surface_form="ない")
    return recognize_pattern(encoded, pattern, "na-adjectives/conjugation", before_pattern)


def recognize_i_adj(encoded):
    pattern = create_word_pattern(tags=[24])
    result = recognize_pattern(encoded, pattern, "i-adjectives")
    if result:
        return {**result,  "coords": [{"start": 0, "end": 0}]}


def recognize_i_conj(encoded):
    before_pattern = create_word_pattern(tags=[24])
    pattern = create_word_pattern(tags=[7])
    return recognize_pattern(encoded, pattern, "i-adjectives/conjugation", before_pattern)


def recognize_yoi_conj(encoded):
    before_pattern = "(" + create_word_pattern(base_form="よい") + "|" + create_word_pattern(base_form="かっこよい") + ")"
    pattern = create_word_pattern(tags=[7])
    return recognize_pattern(encoded, pattern, "adjectives/exception", before_pattern)


def recognize_ru_verb_neg(encoded):
    before_pattern = create_word_pattern(tags=[26])
    pattern = \
        create_word_pattern(surface_form="ない")
    return recognize_pattern(encoded, pattern, "negative verbs/ru-verbs", before_pattern)


def recognize_u_verb_neg(encoded):
    before_pattern = create_word_pattern(tags=[25], romaji="[^ú]*u")
    pattern = \
        create_word_pattern(surface_form="ない")
    result = recognize_pattern(encoded, pattern, "negative verbs/u-verbs ending in u", before_pattern)
    if result:
        return result
    before_pattern = create_word_pattern(tags=[25])
    pattern = \
        create_word_pattern(surface_form="ない")
    return recognize_pattern(encoded, pattern, "negative verbs/u-verbs", before_pattern)


def recognize_verbs(encoded):
    pattern = create_word_pattern(tags=[5])
    result = recognize_pattern(encoded, pattern, 'verbs')
    if result:
        return {**result, "coords": [{"start": 0, "end": 0}]}


def recognize_negative_verbs(encoded):
    result = recognize_ru_verb_neg(encoded)
    if result:
        return result
    result = recognize_u_verb_neg(encoded)
    if result:
        return result
    before_pattern = create_word_pattern(tags=[27])
    pattern = \
        create_word_pattern(surface_form="ない")
    result = recognize_pattern(encoded, pattern, "negative verbs/exception", before_pattern)
    if result:
        return result
    pattern = \
        create_word_pattern(surface_form="ない", tags=[24])
    return recognize_pattern(encoded, pattern, "negative verbs/exception")


def recognize_past_tense(encoded):
    pattern = \
        "(" + create_word_pattern(tags=[5]) + ")" + \
        create_word_pattern(surface_form="(た|だ)", tags=[7])
    matches = re.finditer(pattern, encoded)
    to_return = []
    for match in matches:
        return_dict = {"coords": [{"start": match.start(), "end": match.end()}]}
        if re.search(create_word_pattern(tags=[26]), match.group(1)):
            return_dict["name"] = "past tense/ru-verbs"
            to_return.append(return_dict)
        else:
            base = re.search("ő(.*?);", match.group(1))
            if base.group(1) in ["する", "くる", "行く"]:
                return_dict["name"] = "past tense/exception"
                to_return.append(return_dict)
            else:
                ending = base.group()[-2]
                if ending == "す":
                    return_dict["name"] = "past tense/す ending"
                    to_return.append(return_dict)
                elif ending in ["く", "ぐ"]:
                    return_dict["name"] = "past tense/く, ぐ ending"
                    to_return.append(return_dict)
                elif ending in ["む", "ぶ", "ぬ"]:
                    return_dict["name"] = "past tense/む, ぶ, ぬ ending"
                    to_return.append(return_dict)
                elif ending in "るつう":
                    return_dict["name"] = "past tense/る, つ, う ending"
                    to_return.append(return_dict)
    return to_return


def recognize_verb_negative_past(encoded):
    before_pattern = "(" + create_word_pattern(tags=[5]) + "|" + create_word_pattern(tags=[1]) + ")"
    pattern = create_word_pattern(surface_form="なかっ", base_form="ない") + create_word_pattern(surface_form="た")
    return recognize_pattern(encoded, pattern, "verb negative past", before_pattern)


def recognize_wo(encoded):
    pattern = \
        create_word_pattern(tags=[3], surface_form="を")
    return recognize_pattern(encoded, pattern, "The direct object を particle")


def recognize_ni(encoded):
    pattern = \
        create_word_pattern(tags=[3], surface_form="に")
    return recognize_pattern(encoded, pattern, "The target に particle")


def recognize_he(encoded):
    pattern = \
        create_word_pattern(tags=[3], surface_form="へ")
    return recognize_pattern(encoded, pattern, "The directional へ particle")


def recognize_de(encoded):
    pattern = \
        create_word_pattern(tags=[3], surface_form="で")
    return recognize_pattern(encoded, pattern, "The contextual で particle")


def recognize_de_with_nan(encoded):
    before_pattern = create_word_pattern(surface_form="何")
    pattern = \
        create_word_pattern(tags=[3], surface_form="で")
    return recognize_pattern(encoded, pattern, "Using で with 何", before_pattern)


def recognize_location_topic(encoded):
    pattern = \
        create_word_pattern(tags=[3], surface_form="(に|で)") + \
        create_word_pattern(tags=[3], surface_form="(は|も)")
    return recognize_pattern(encoded, pattern, "When location is the topic")


def recognize_transitive(encoded):
    pattern = \
        create_word_pattern(tags=[3], surface_form="を") + \
        "(?=" + create_word_pattern(tags=[5]) + ")"
    result = recognize_pattern(encoded, pattern, "transitive verbs")
    if result:
        return {**result, "coords": [{"start": 0, "end": 0}]}


def recognize_intransitive(encoded):
    pattern = \
        create_word_pattern(tags=[3], surface_form="(は|が)") + \
        "(?=" + create_word_pattern(tags=[5]) + ")"
    result = recognize_pattern(encoded, pattern, "intransitive verbs")
    if result:
        return {**result, "coords": [{"start": 0, "end": 0}]}


def recognize_sob_adj(encoded):
    before_pattern = create_word_pattern(tags=[1])
    pattern = \
        "((" + create_word_pattern(tags=[7], surface_form="な") + ")|(" + create_word_pattern(
            surface_form="じゃ") + "))+" + \
        "(?=" + create_word_pattern(tags=[1]) + ")"
    return recognize_pattern(encoded, pattern, "state-of-being clause as adjective", before_pattern)


def recognize_verb_adj(encoded):
    before_pattern = create_word_pattern(tags=[5])
    pattern = \
        "(" + create_word_pattern(tags=[7]) + ")*" + \
        "(?=" + create_word_pattern(tags=[1]) + ")"
    return recognize_pattern(encoded, pattern, "verb clause as adjective", before_pattern)


def recognize_to(encoded):
    pattern = \
        create_word_pattern(tags=[3], surface_form="と")
    return recognize_pattern(encoded, pattern, "the inclusive と particle")


def recognize_listing_particle(encoded):
    pattern = create_word_pattern(tags=[29])
    return recognize_pattern(encoded, pattern, "the vauge listing や and とか particles")


def recognize_explanatory_no(encoded):
    pattern = create_word_pattern(tags=[1], surface_form="ん", base_form="ん")
    explanatory = recognize_pattern(encoded, pattern, "the の particle/explanatory の")
    if explanatory:
        return explanatory


def recognize_no(encoded):
    pattern = create_word_pattern(tags=[3], surface_form="の")
    no = recognize_pattern(encoded, pattern, "the の particle")
    if no:
        return no
    pattern = create_word_pattern(tags=[1], surface_form="の")
    omit = recognize_pattern(encoded, pattern, "the の particle/omitting modified noun")
    if omit:
        return omit


def recognize_i_adverb(encoded):
    pattern = create_word_pattern(tags=[24], surface_form=".+く")
    return recognize_pattern(encoded, pattern, "i-adverb")


def recognize_na_adverb(encoded):
    before_pattern = create_word_pattern(tags=[1, 16])
    pattern = create_word_pattern(tags=[3], surface_form="に")
    return recognize_pattern(encoded, pattern, "na-adverb", before_pattern)


def recognize_yo_ne_or_yone_end(encoded):
    yo_pattern = create_word_pattern(tags=[3], surface_form="よ")
    ne_pattern = create_word_pattern(tags=[3], surface_form="ね")
    yo_match = recognize_pattern(encoded, yo_pattern, "よ sentence ending")
    ne_match = recognize_pattern(encoded, ne_pattern, "ね sentence ending")
    if yo_match and not ne_match:
        return yo_match
    if ne_match and not yo_match:
        return ne_match
    if yo_match and ne_match:
        return {
            "name": "よね sentence ending",
            "coords": [
                {
                    "start": yo_match["coords"][0]["start"],
                    "end": yo_match["coords"][0]["end"]
                }
            ]
        }


def recognize_masu(encoded):
    pattern = create_word_pattern(base_form="ます", tags=[7]) + "(" + create_word_pattern(surface_form="た",
                                                                                        tags=[7]) + ")?"
    return recognize_pattern(encoded, pattern, 'using masu')


def recognize_te(encoded):
    pattern = create_word_pattern(surface_form="なく") + create_word_pattern(surface_form="(て|で)", tags=[3, 35])
    result = recognize_pattern(encoded, pattern, "te form negative")
    if result:
        return result
    pattern = create_word_pattern(surface_form="(て|で)", tags=[3, 35])
    recognized = recognize_pattern(encoded, pattern, "te form positive")
    if recognized:
        return recognized


def recognize_desu(encoded):
    pattern = create_word_pattern(surface_form="です", tags=[7])
    return recognize_pattern(encoded, pattern, "using desu")


def recognize_formal_past(encoded):
    pattern = create_word_pattern(base_form="です", surface_form="でし", tags=[7]) + create_word_pattern(surface_form="た")
    return recognize_pattern(encoded, pattern, "formal past")


def recognize_ka(encoded):
    pattern = create_word_pattern(surface_form="か", tags=[3, 38])
    return recognize_pattern(encoded, pattern, "question ka")


def recognize_kara(encoded):
    pattern = create_word_pattern(surface_form="から", tags=[3, 35])
    return recognize_pattern(encoded, pattern, "kara")


def recognize_dearu(encoded):
    pattern = "((" \
                  + create_word_pattern(surface_form="で", base_form="(だ|で)")\
                  + create_word_pattern(tags=[3], surface_form="は") \
                  + create_word_pattern(surface_form="ない") \
                + ")|(" \
                    + create_word_pattern(surface_form="で", base_form="だ") \
                    + create_word_pattern(surface_form="ある") \
                + "))"
    return recognize_pattern(encoded, pattern, "dearu")


def recognize_kamoshirenai(encoded):
    pattern = \
        create_word_pattern(surface_form="かも", tags=[3]) \
        + create_word_pattern(surface_form="(しれ|知れ)", base_form="(しれる|知れる)") \
        + create_word_pattern(surface_form="ない", base_form="ない")
    result = recognize_pattern(encoded, pattern, "kamoshirenai")
    if result:
        return result
    pattern = \
        create_word_pattern(surface_form="かも", tags=[3]) \
        + create_word_pattern(surface_form="(しれ|知れ)", base_form="(しれる|知れる)") \
        + create_word_pattern(base_form="ます", surface_form="ませ") \
        + create_word_pattern(surface_form="ん", base_form="ん")
    result = recognize_pattern(encoded, pattern, "kamoshirenai")
    if result:
        return result
    pattern = \
        create_word_pattern(surface_form="かも", tags=[3]) \
        + create_word_pattern(surface_form="(しれ|知れ)", base_form="(しれる|知れる)") \
        + create_word_pattern(surface_form="ん", base_form="ん")
    result = recognize_pattern(encoded, pattern, "kamoshirenai")
    if result:
        return result
    pattern = \
        create_word_pattern(surface_form="かも", tags=[3])
    result = recognize_pattern(encoded, pattern, "kamoshirenai")
    if result:
        return result


def recognize_deshou(encoded):
    pattern = create_word_pattern(base_form="です", surface_form="でしょ") \
              + create_word_pattern(base_form="う")
    return recognize_pattern(encoded, pattern, "deshou")


def recognize_nara(encoded):
    pattern = create_word_pattern(surface_form="なら", base_form="だ") \
              + "(" + create_word_pattern(base_form="ば", surface_form="ば") + ")?"
    return recognize_pattern(encoded, pattern, "nara")


def recognize_arimasen(encoded):
    pattern = create_word_pattern(base_form="ある", surface_form="あり") \
              + create_word_pattern(base_form="ます", surface_form="ませ") \
              + create_word_pattern(base_form="ん", surface_form="ん") \
              + "(" + create_word_pattern(surface_form="でし") + create_word_pattern(surface_form="た") + ")?"
    return recognize_pattern(encoded, pattern, "arimasen")


def recognize_potential_form(encoded):
    pattern = create_word_pattern(base_form="(られる|れる)") + "(" + create_word_pattern(surface_form="ない") + ")?"
    return recognize_pattern(encoded, pattern, "potential form")


def recognize_darou(encoded):
    pattern = create_word_pattern(base_form="だ", surface_form="だろ") + create_word_pattern(surface_form="う")
    return recognize_pattern(encoded, pattern, "darou")


def recognize_enduring_state(encoded):
    pattern = "((" + create_word_pattern(surface_form="てる") \
              + ")|(" + create_word_pattern(base_form="て", tags=[3, 35]) + create_word_pattern(surface_form="いる") + "))"
    return recognize_pattern(encoded, pattern, "enduring states")


def recognize_contradiction(encoded):
    pattern = create_word_pattern(surface_form="(が|けど)", tags=[35])
    return recognize_pattern(encoded, pattern, "contradiction")


def recognize_toiu(encoded):
    pattern = "(" + create_word_pattern(surface_form="という") \
              + "|(" + create_word_pattern(surface_form="と") + create_word_pattern(surface_form="言う") + "))"
    return recognize_pattern(encoded, pattern, "toiu")


def recognize_grammar(sent, kuro_server):
    tagged = pos_tag(sent, kuro_server)
    encoded = encode_tags(tagged)
    grammars = [
        recognize_da,
        recognize_negative_state_of_being,
        recognize_past_state_of_being,
        recognize_past_negative,
        recognize_topic_particle,
        recognize_inclusive_particle,
        recognize_identifier_particle,
        recognize_na_adj,
        recognize_na_conj,
        recognize_i_adj,
        recognize_i_conj,
        recognize_yoi_conj,
        recognize_verbs,
        recognize_negative_verbs,
        recognize_past_tense,
        recognize_verb_negative_past,
        recognize_wo,
        recognize_ni,
        recognize_he,
        recognize_de,
        recognize_de_with_nan,
        recognize_location_topic,
        recognize_transitive,
        recognize_intransitive,
        recognize_sob_adj,
        recognize_verb_adj,
        recognize_to,
        recognize_listing_particle,
        recognize_no,
        recognize_explanatory_no,
        recognize_i_adverb,
        recognize_na_adverb,
        recognize_yo_ne_or_yone_end,
        recognize_masu,
        recognize_te,
        recognize_desu,
        recognize_formal_past,
        recognize_ka,
        recognize_kara,
        recognize_dearu,
        recognize_kamoshirenai,
        recognize_deshou,
        recognize_nara,
        recognize_arimasen,
        recognize_potential_form,
        recognize_darou,
        recognize_enduring_state,
        recognize_contradiction,
        recognize_toiu
    ]
    found = [x(encoded) for x in grammars]
    found = flatten([x for x in found if x is not None])
    return found
