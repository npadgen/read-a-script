#!/usr/bin/env python3
#
# pylint: disable=line-too-long

"""Usage:
  script_learner.py [-h] [-c CONFIG_FILE] [-dqLRV] [-r ROLE]... [-s SCENES] [-f SCRIPT_FILE]

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
  -R, --list-roles                        List all known roles and exit
  -f SCRIPT_FILE, --file SCRIPT_FILE      The Fountain-formatted script file

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

defaults:
  # the default role to use (case-insensitive)
  role: BONES
  # the default script file to load
  script-file: the-play-what-i-wrote.fountain
"""

import enum
import os
import re
import subprocess
import sys

import docopt
import readchar
from jouvence.parser import JouvenceParser
from loguru import logger
from macos_speech import Synthesizer, Voice
from ruamel.yaml import YAML

from read_a_script.utils import ElementType, mixrange

ACTION_CHARACTER = "_ACTION"
DEFAULT_CHARACTER = "_DEFAULT"
DEFAULT_CONFIG = __doc__.split("---\n")[1]

DEFAULT_VOICE = "Daniel"


class LearningMethod(enum.Enum):
    """enum"""

    PAUSE_AND_DISPLAY = enum.auto()
    DISPLAY_AND_PAUSE = enum.auto()
    WAIT_FOR_INPUT = enum.auto()
    SPEAK_AND_DISPLAY = enum.auto()


class Actor:

    """
    An Actor displays lines that it is given, while reading them out in its selected voice.
    """

    def __init__(self, config, role, voice: Voice):
        self.role = role
        self.voice = voice
        self.synth = Synthesizer(voice=voice.name)
        self.config = config
        if "rate" in self.config["options"]:
            self.synth.rate = int(self.config["options"]["rate"])

    def read_line(self, line):
        "Display a line and speak it aloud."
        self.display_line(line)
        self.speak_line(line)

    def speak_line(self, line):
        "Speak a line of action aloud."
        if self.role == ACTION_CHARACTER and not self.config["options"].get(
            "speak-action", True
        ):
            return
        if line:
            self.synth.say(line)

    def display_line(self, line, include_character=True):
        "Display a line of action without speaking it."
        if (
            self.role is not None
            and self.role != ACTION_CHARACTER
            and include_character
        ):
            self.display_character()
        print(line.strip() + "\n")

    def display_character(self):
        "Display the character's name."
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
            self.learning_method = LearningMethod(int(lm))
        if self.learning_method == LearningMethod.WAIT_FOR_INPUT:
            self.print_help_interactive()

    def _mute_unmute_output(self, muted: bool):
        subprocess.run(
            ["osascript", "-e", f"set volume output muted {muted}"], check=False
        )

    def silent_speak_line(self, line):
        """
        Same as speak_line but mutes the volume - so it effectively pauses for the right length of time.
        :param line:
        :return:
        """
        if not line:
            return
        self._mute_unmute_output(True)
        self.synth.say(line)
        self._mute_unmute_output(False)

    def speak_line(self, line):
        if self.learning_method == LearningMethod.SPEAK_AND_DISPLAY:
            return super().speak_line(line)
        else:
            return self.silent_speak_line(line)

    def read_line_pause_then_display(self, line):
        """Silently read the line, then display it"""
        self.display_character()
        self.silent_speak_line(line)
        self.display_line(line, include_character=False)

    def read_line_display_then_pause(self, line):
        """Display a line, then silently read it"""
        self.display_line(line)
        self.silent_speak_line(line)

    def read_line_as_actor(self, line):
        """Read the line in the way the superclass would read it"""
        super().read_line(line)

    def read_line_interactive(self, line):
        """Read the line one word at a time"""
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
                self.synth.say(hint)
                sys.stdout.write(hint + " ")
                sys.stdout.flush()
                if line is None:
                    sys.stdout.write("\n")
                    return
            elif say_it in (" ", "n"):
                print(line)
                return
            elif say_it in ("\x013", "y"):
                print(line)
                self.synth.say(line)
                return
            else:
                self.print_help_interactive()

    def print_help_interactive(self):
        """
        Give some help to the poor frustrated actor
        who can't remember how to use interactive mode
        """
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
            logger.warning(f"Unknown learning method {self.learning_method}!")


# pylint: disable=too-many-instance-attributes
class ScriptReciter:
    """
    Read out the script
    """

    def __init__(self, script_file, roles, config):
        self.parser = JouvenceParser()
        self.d = self.parser.parse(script_file)
        self.roles = list(map(lambda x: x.upper(), roles))
        self.config = config

        self.current_role = None
        self.current_actor = None

        self.voices = dict((v.name.capitalize(), v) for v in Synthesizer().voices)
        self.actors = {}

    def learn(self, scenes=None):
        """
        Learn the selected scenes
        """
        print("You are learning: " + ", ".join(self.roles))
        if scenes is None:
            scenes = self.d.scenes
        else:
            scenes = [self.d.scenes[i - 1] for i in scenes]
        for scene in scenes:
            self.learn_scene(scene)

    def list_scenes(self):
        """
        List all the scenes in the play
        """
        for i, scene in enumerate(self.d.scenes, 1):
            print(f"{i:-8d}: {scene.header}")

    def list_roles(self):
        """
        List all the roles in the play
        """
        roles = set()
        for scene in self.d.scenes:
            roles.update(set(p.text for p in scene.paragraphs if p.type == ElementType.CHARACTER.value))
        for role in sorted(roles):
            print(role)

    def list_voices(self):
        """
        List all the voices installed on this machine
        """
        print("Known voices: ")
        for voice in self.voices.values():
            print(f"\t{voice.name} (f{voice.lang})")

    def learn_scene(self, scene):
        """
        Learn an individual scene
        """
        self.current_actor = self.get_actor(ACTION_CHARACTER)
        self.current_actor.read_line("Scene: " + (scene.header or ""))
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

    def get_actor(self, character_name) -> Actor:
        """
        Get the Actor object for the given character
        """
        if character_name is not None:
            character_name = character_name.strip()
        if character_name in self.actors:
            return self.actors[character_name]
        if character_name in self.config["voices"]:
            voice_name = self.config["voices"][character_name].capitalize()
            if voice_name in self.voices:
                voice = self.voices[voice_name]
            else:
                logger.warning(
                    f"{voice_name} is not in the list of known voices - using {DEFAULT_VOICE}"
                )
                voice = self.voices[DEFAULT_VOICE]
        else:
            if character_name != ACTION_CHARACTER:
                logger.warning(
                    f"Could not find {character_name} in configuration.voices - using {DEFAULT_VOICE}"
                )
            voice = self.voices[DEFAULT_VOICE]
        if character_name is None:
            actor = Actor(self.config, None, voice)
        elif character_name in self.roles:
            actor = LearningActor(self.config, character_name, voice)
        else:
            actor = Actor(self.config, character_name, voice)
        self.actors[character_name] = actor
        return actor


@logger.catch
def main():
    """
    The show must go on
    """
    opts = docopt.docopt(__doc__, sys.argv[1:])

    if "--config" in opts and os.path.exists(opts["--config"]):
        # pylint: disable=W1514
        config = YAML().load(open(opts["--config"]).read())
    else:
        config = YAML().load(DEFAULT_CONFIG)

    if DEFAULT_CHARACTER in config["voices"]:
        # pylint: disable=W0603
        global DEFAULT_VOICE
        DEFAULT_VOICE = config["voices"][DEFAULT_CHARACTER]
    role = script_file = None
    if "defaults" in config:
        if "role" in config["defaults"]:
            role = config["defaults"]["role"]
            if isinstance(role, str):
                role = [role]
        if "script-file" in config["defaults"]:
            script_file = config["defaults"]["script-file"]
    if role is None:
        role = opts["--role"]
    if script_file is None:
        script_file = opts["--file"]
    learner = ScriptReciter(script_file, role, config)

    if opts["--list-scenes"]:
        learner.list_scenes()
    elif opts["--list-voices"]:
        learner.list_voices()
    elif opts["--list-roles"]:
        learner.list_roles()
    elif opts["--scenes"] == "all":
        learner.learn()
    else:
        learner.learn(mixrange(opts["--scenes"]))


if __name__ == "__main__":
    main()
