#!/usr/bin/env python3

"""Usage:
  script_learner.py [-h] [-c CONFIG_FILE] [-dqLV] -r ROLE [-r ROLE]... [-s SCENES] SCRIPT_FILE

Options:
  -c CONFIG_FILE, --config CONFIG_FILE    Read additional configuration from CONFIG_FILE [default: ./config.yml]
                                          If CONFIG_FILE does not exist, a default config will be used;
                                          run this program with -h to see the default config.
  -d, --debug                             Produce additional output
  -h, --help                              Document how to use this program
  -q, --quiet                             Produce minimal output
  -r ROLE, --role ROLE                    Role(s) to learn
  -s SCENES, --scenes SCENES              Scene(s) to learn [default: all]
  -L, --list-scenes                       List all the scenes and exit
  -V, --list-voices                       List all known voices and exit
  SCRIPT_FILE                             The Fountain-formatted script file

For more information about formatting SCRIPT_FILE, see http://fountain.io

If the configuration file cannot be found, a default configuration will be used instead.
The default configuration is:
---
voices:
  BONES: Tom
  KIRK: Alex
  SPOCK: Fred
  _DEFAULT: Daniel
  _ACTION: Moira
  
options:
  # the rate at which speech will be spoken
  rate: 150
  # whether to speak stage directions and parenthetical actions
  speak-action: true
  # how to display lines for learning: valid values are:
  #  PAUSE_AND_DISPLAY
  #  DISPLAY_AND_PAUSE
  #  WAIT_FOR_INPUT
  #  SPEAK_AND_DISPLAY
  # or an integer from 1 to 4
  learning-method: PAUSE_AND_DISPLAY
"""

from .utils import ElementType, mixrange
from jouvence.parser import JouvenceParser
import enum
import os
import re
import readchar
import logging
import subprocess
import docopt
import sys
from ruamel.yaml import YAML
import pyttsx3

ACTION_CHARACTER = "_ACTION"
DEFAULT_CHARACTER = "_DEFAULT"
DEFAULT_CONFIG = __doc__.split("---\n")[1]
LOGGER = logging.getLogger(sys.argv[0])
LOGGER.addHandler(logging.StreamHandler())

DEFAULT_VOICE = "Daniel"


class LearningMethod(enum.Enum):
    PAUSE_AND_DISPLAY = enum.auto()
    DISPLAY_AND_PAUSE = enum.auto()
    WAIT_FOR_INPUT = enum.auto()
    SPEAK_AND_DISPLAY = enum.auto()


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
        if self.role == ACTION_CHARACTER and not self.config["options"].get(
            "speak-action", True
        ):
            return
        self.engine.setProperty("voice", self.voice.id)
        self.engine.say(line)
        self.engine.runAndWait()

    def display_line(self, line, include_character=True):
        if (
            self.role is not None
            and self.role != ACTION_CHARACTER
            and include_character
        ):
            self.display_character()
        print(line.strip() + "\n")

    def display_character(self):
        print(f"{self.role.upper()}: ", end="", flush=True)


class LearningActor(Actor):

    """
    A LearningActor is like an Actor, but is intended for the person using the program to learn the lines in question.
    It can work in the following ways:

    - it pauses for the length of time it would take for the line to be read, then displays the line;
    - it waits for a keypress, then displays the next word or the entire line (depending on what key is pressed);
    - it displays the line, then pauses for the length of time it would take for the line to be read;
    - or, it behaves exactly like an Actor.
    """

    def __init__(self, *args, **kwargs):
        super(LearningActor, self).__init__(*args, **kwargs)
        lm = self.config["options"]["learning-method"]
        try:
            self.learning_method = LearningMethod[lm]
        except KeyError:
            self.learning_method = LearningMethod(int[lm])
        if self.learning_method == LearningMethod.WAIT_FOR_INPUT:
            self.print_help_interactive()

    def silent_speak_line(self, line):
        """
        Same as speak_line but mutes the volume - so it effectively pauses for the right length of time.
        :param line:
        :return:
        """
        self.engine.setProperty("voice", self.voice.id)
        volume = self.engine.getProperty("volume")
        self.engine.setProperty("volume", 0)
        self.engine.say(line)
        self.engine.runAndWait()
        self.engine.setProperty("volume", volume)

    def speak_line(self, line):
        if self.learning_method == LearningMethod.SPEAK_AND_DISPLAY:
            return super().speak_line(line)
        else:
            return self.silent_speak_line(line)

    def read_line_pause_then_display(self, line):
        self.display_character()
        self.silent_speak_line(line)
        self.display_line(line, include_character=False)

    def read_line_display_then_pause(self, line):
        self.display_line(line)
        self.silent_speak_line(line)

    def read_line_as_actor(self, line):
        super(LearningActor, self).read_line(line)

    def read_line_interactive(self, line):
        self.engine.setProperty("voice", self.voice.id)
        self.display_character()
        while True:
            sys.stdout.flush()
            say_it = readchar.readchar().lower()
            if say_it == "\x03":
                raise KeyboardInterrupt
            elif say_it == "\x04":
                raise EOFError
            elif say_it == "h":
                if " " in line:
                    hint, line = re.split(r"\s+", line, 1)
                else:
                    hint, line = line, None
                self.engine.say(hint)
                self.engine.runAndWait()
                sys.stdout.write(hint + " ")
                sys.stdout.flush()
                if line is None:
                    sys.stdout.write("\n")
                    return
            elif say_it == " " or say_it == "n":
                print(line)
                return
            elif say_it == "\x013" or say_it == "y":
                print(line)
                self.engine.say(line)
                self.engine.runAndWait()
                return
            else:
                self.print_help_interactive()

    def print_help_interactive(self):
        print()
        print("  Hit H for a hint, enter or Y to read the whole line,")
        print("  space or N to skip to the next line without reading,")
        print("  or Ctrl-C or Ctrl-D to exit")

    def read_line(self, line):
        if self.learning_method == LearningMethod.PAUSE_AND_DISPLAY:
            self.read_line_pause_then_display(line)
        elif self.learning_method == LearningMethod.DISPLAY_AND_PAUSE:
            self.read_line_display_then_pause(line)
        elif self.learning_method == LearningMethod.WAIT_FOR_INPUT:
            self.read_line_interactive(line)
        elif self.learning_method == LearningMethod.SPEAK_AND_DISPLAY:
            self.read_line_as_actor(line)
        else:
            LOGGER.warning(f"Unknown learning method {self.learning_method}!")


class ScriptReciter:
    def __init__(self, script_file, roles, config):
        self.parser = JouvenceParser()
        self.d = self.parser.parse(script_file)
        self.roles = list(map(lambda x: x.upper(), roles))
        self.config = config

        self.current_role = None
        self.current_actor = None

        self.engine: pyttsx3.Engine = pyttsx3.init()
        if "rate" in self.config["options"]:
            self.engine.setProperty("rate", int(self.config["options"]["rate"]))
        self.voices = dict(
            (v.name.capitalize(), v) for v in self.engine.getProperty("voices")
        )
        self.actors = {}

    def learn(self, scenes=None):
        print("You are learning: " + ", ".join(self.roles))
        if scenes is None:
            scenes = self.d.scenes
        else:
            scenes = [self.d.scenes[i - 1] for i in scenes]
        for scene in scenes:
            self.learn_scene(scene)

    def list_scenes(self):
        for i, scene in enumerate(self.d.scenes, 1):
            print("{:-8d}: {}".format(i, scene.header))

    def list_voices(self):
        print("Known voices: ")
        for voice in self.voices.values():
            print(f"\t{voice.name} ({', '.join(voice.languages)})")

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

    if "--config" in opts and os.path.exists(opts["--config"]):
        config = YAML().load(open(opts["--config"]).read())
    else:
        config = YAML().load(DEFAULT_CONFIG)

    if DEFAULT_CHARACTER in config["voices"]:
        global DEFAULT_VOICE
        DEFAULT_VOICE = config["voices"][DEFAULT_CHARACTER]
    learner = ScriptReciter(opts["SCRIPT_FILE"], opts["--role"], config)

    if opts["--list-scenes"]:
        learner.list_scenes()
    elif opts["--list-voices"]:
        learner.list_voices()
    elif opts["--scenes"] == "all":
        learner.learn()
    else:
        learner.learn(mixrange(opts["--scenes"]))


if __name__ == "__main__":
    main()
