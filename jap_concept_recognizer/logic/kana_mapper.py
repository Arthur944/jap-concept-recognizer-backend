# Create cards from the supplied words
import re
import romkan

hiragana = "かたさははせけてへへくすつふふこそとほほきちしひひあならわまやえねれめうぬるむゆおのろをもよいにりみん"
katakana = "カタサハハセケテヘヘクスツフフコソトホホキチシヒヒアナラワマヤエネレメウヌルムユオノロヲモヨイニリミン"
romanji = ["ka", "ta", "sa", "ha", "ha", "se", 'ke', 'te', 'he', 'he', 'ku', 'su', 'tsu', 'fu', 'fu', 'ko', 'so',
           'to', "ho", "ho", "ki", "chi", "shi", "hi","hi", "a", "na", "ra", "wa", "ma", "ya", "e", "ne", "re", "me",
           "u", "nu", "ru", "mu", "yu", "o", "no", "ro", "wo", "mo", "yo", "i", "ni", "ri", "mi", "n"]
muddy_hiragana = "がだざばぱぜげでべぺぐずづぶぷごぞどぼぽぎぢじびぴ"
muddy_katakana = "ガダザバパゼゲデベペグズヅブプゴゾドボポギヂジビピ"


class Concept:
    def __init__(self, id, name, character, muddy=None):
        self.id = id
        self.name = name
        self.character = character
        self.muddy = muddy


class KanaMapper:
    def __init__(self, concept_reference):
        lines = concept_reference.splitlines()
        self.kana = []
        self.additional_sounds_id = None
        self.little_tsu_id = None
        self.long_vowel_id = None
        self.y_vowel_id = None
        self.concepts = [{"id": x.split(";")[0], "parent_id": x.split(";")[1], "name": x.split(";")[2].strip()} for x in lines[1:]]
        for line in lines[1:]:
            id, parent_id, name = line.split(";")
            name = name.strip()
            character = name
            if character in hiragana:
                if hiragana.index(character) < 25:
                    self.kana.append(Concept(id, name, character, muddy=muddy_hiragana[hiragana.index(character)]))
                self.kana.append(Concept(id, name, character))
            elif character in katakana:
                if katakana.index(character) < 25:
                    if len(katakana) > katakana.index(character) + 1 and katakana[katakana.index(character) + 1] == character:
                        self.kana.append(Concept(id, name, character, muddy=muddy_katakana[katakana.index(character) + 1]))
                    self.kana.append(Concept(id, name, character, muddy=muddy_katakana[katakana.index(character)]))
                self.kana.append(Concept(id, name, character))
            if 'Voiced' in name:
                self.additional_sounds_id = id
            if name == "Little tsu":
                self.little_tsu_id = id
            if name == "Long vowel sound":
                self.long_vowel_id = id
            if name == "Y vowel sound":
                self.y_vowel_id = id

    def concepts_to_character(self, character):
        if character == "っ":
            return [self.little_tsu_id]
        if character == "ー":
            return [self.long_vowel_id]
        if character in "ゃゅょャュョ":
            return [self.y_vowel_id]
        for concept in self.kana:
            if concept.character == character:
                return [concept.id]
            if concept.muddy == character:
                return [concept.id, self.additional_sounds_id]
        return []

    def reverse_concept(self, concept):
        if 'read' in concept and 'write' not in concept:
            return concept.replace("read", "write")
        if "write" in concept and "read" not in concept:
            return concept.replace("write", "read")
        return concept

    def word_prereqs(self, word):
        prereqs = []
        for character in word:
            prereqs += self.concepts_to_character(character)
        return [str(x) for x in list(set(prereqs))]

    def word_to_romanji(self, word):
        return romkan.to_roma(word)
