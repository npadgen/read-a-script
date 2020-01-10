#!/usr/bin/env python3

"""Usage:
  script_learner.py [-c CONFIG_FILE] [-d] [-q] -r ROLE [-r ROLE ... ] SCRIPT_FILE

Options:
  -c CONFIG_FILE, --config CONFIG_FILE    Read additional configuration from CONFIG_FILE
  -d, --debug                             Produce additional output
  -q, --quiet                             Produce minimal output
  -r ROLE                                 Role(s) to learn
  SCRIPT_FILE                             The Fountain-formatted script file

For more information about formatting SCRIPT_FILE, see http://fountain.io
"""

from utils import ElementType, mixrange
from jouvence.parser import JouvenceParser
from jouvence.renderer import BaseTextRenderer
import os
import re
import logging
import subprocess
import docopt
import sys
from ruamel.yaml import YAML
import pyttsx3

ACTION_CHARACTER = "_ACTION"
DEFAULT_CHARACTER = "_DEFAULT"

LOGGER = logging.getLogger(sys.argv[0])
LOGGER.addHandler(logging.StreamHandler())

DEFAULT_VOICE = "Daniel"


class Actor:

    """
    An Actor displays lines that it is given, while reading them out in its selected voice.
    """

    def __init__(self, config, role, voice, engine: pyttsx3.Engine):
        self.role = role
        self.voice = voice
        self.engine = engine
        self.config = config

    def read_line(self, line):
        self.display_line(line)
        self.speak_line(line)

    def speak_line(self, line):
        if self.role == ACTION_CHARACTER and not self.config["config"].get("speak-action", True):
            return
        self.engine.setProperty("voice", self.voice.id)
        self.engine.say(line)
        self.engine.runAndWait()

    def display_line(self, line):
        if self.role is not None and self.role != ACTION_CHARACTER:
            print(f"{self.role.upper()}: ", end="")
        print(line)


class LearningActor(Actor):

    """
    A LearningActor is like an Actor, but is intended for the person using the program to learn the lines in question.
    It can work in the following ways:

    - it pauses for the length of time it would take for the line to be read, then displays the line;
    - it waits for a keypress, then displays the next word or the entire line (depending on what key is pressed);
    - it displays the line, then pauses for the length of time it would take for the line to be read;
    - or, it behaves exactly like an Actor.
    """

    def silent_speak_line(self, line):
        self.engine.setProperty("voice", self.voice.id)
        volume = self.engine.getProperty("volume")
        self.engine.setProperty("volume", 0)
        self.engine.say(line)
        self.engine.runAndWait()
        self.engine.setProperty("volume", volume)

    def speak_line(self, line):
        return self.silent_speak_line(line)


class ScriptReciter:
    def __init__(self, script_file, roles, config):
        self.parser = JouvenceParser()
        self.d = self.parser.parse(script_file)
        self.roles = roles
        self.config = config

        self.current_role = None
        self.current_actor = None

        self.engine: pyttsx3.Engine = pyttsx3.init()
        if "rate" in self.config["config"]:
            self.engine.setProperty("rate", int(self.config["config"]["rate"]))
        self.voices = dict(
            (v.name.capitalize(), v) for v in self.engine.getProperty("voices")
        )
        print("Known voices: " + ", ".join(self.voices.keys()))
        print("You are learning: " + ", ".join(roles))
        self.actors = {}

    def learn(self):
        for scene in self.d.scenes:
            self.learn_scene(scene)

    def learn_scene(self, scene):
        self.current_actor = self.get_actor(ACTION_CHARACTER)
        self.current_actor.read_line("Scene: " + scene.header)
        for p in scene.paragraphs:
            p_type = ElementType(p.type)
            if p_type in (
                ElementType.ACTION,
                ElementType.CENTERED_ACTION,
                ElementType.TRANSITION,
                ElementType.SYNOPSIS,
            ):
                self.current_actor = self.get_actor(ACTION_CHARACTER)
                self.current_actor.read_line(p.text)
            elif p_type == ElementType.CHARACTER:
                self.current_actor = self.get_actor(p.text)
            elif p_type in (ElementType.DIALOG, ElementType.LYRICS):
                self.current_actor.read_line(p.text)
            elif p_type == ElementType.PARENTHETICAL:
                self.get_actor(ACTION_CHARACTER).read_line(p.text)
            else:
                self.get_actor(DEFAULT_CHARACTER).read_line(p.text)

    def get_actor(self, character_name):
        if character_name is not None:
            character_name = character_name.strip()
        if character_name in self.actors:
            return self.actors[character_name]
        if character_name in self.config["voices"]:
            voice_name = self.config["voices"][character_name].capitalize()
            if voice_name in self.voices:
                voice = self.voices[voice_name]
            else:
                LOGGER.warning(
                    f"{voice_name} is not in the list of known voices - using {DEFAULT_VOICE}"
                )
                voice = self.voices[DEFAULT_VOICE]
        else:
            if character_name != ACTION_CHARACTER:
                LOGGER.warning(
                    f"Could not find {character_name} in configuration.voices - using {DEFAULT_VOICE}"
                )
            voice = self.voices[DEFAULT_VOICE]
        if character_name is None:
            actor = Actor(self.config, None, voice, self.engine)
        elif character_name in self.roles:
            actor = LearningActor(self.config, character_name, voice, self.engine)
        else:
            actor = Actor(self.config, character_name, voice, self.engine)
        self.actors[character_name] = actor
        return actor


def main():
    opts = docopt.docopt(__doc__, sys.argv[1:])
    if "-c" in opts:
        config = YAML().load(open(opts["-c"]).read())
    else:
        config = YAML().load(open("config.yml").read())
    if DEFAULT_CHARACTER in config["voices"]:
        global DEFAULT_VOICE
        DEFAULT_VOICE = config["voices"][DEFAULT_CHARACTER]
    learner = ScriptReciter(opts["SCRIPT_FILE"], opts["-r"], config)
    learner.learn()


if __name__ == "__main__":
    main()
