#!/usr/bin/env python3
#
# $Id$

####################################################################
# LEGACY - DO NOT USE!
#
# This is the original version of read-a-script,
# which was completely rewritten as `read_a_script/script_learner.py`.
# It's still here because I can't bear to let it go,
# but it is no more; it has ceased to be; it's expired and gone
# to meet its maker; it's hopped the twig; it's curled up its
# tootsies; it's shuffled off this mortal coil; it's rung
# down the curtain and joined the bleedin' choir invisibule.
# Vis-a-vis Pythonic processes, it's had its lot.
# All statements to the effect that this script is still a going
# concern are from now on inoperative.
# This is an ex-read-a-script.
####################################################################

import os
import re
import sys
import subprocess
import argparse
import readchar
import textwrap
import json
import logging

from utils import mixrange

LOGGER = logging.getLogger("read-a-script")
LOGGER.addHandler(logging.StreamHandler())

VOICES = {
    # Spring and Port Wine
    "rafe": "tom",
    "arthur": "lee",
    "harold": "daniel",
    "wilfred": "oliver",
    "daisy": "fiona",
    "florence": "kate",
    "hilda": "serena",
    "betsy jane": "karen",
    None: "tom",
    "stage directions": "moira",
    "all": "daniel",
    # Joining The Club
    "tom": "tom",
    "jenny": "karen",
    # The Pigeon with the Silver Foot
    "waiter": "luca",
    "mary": "kate",
    "joanna": "serena",
    "bianca": "karen",
    "lover": "lee",
    "customer": "alice",
    "beggar": "alice",
    "single female voice": "allison",
}


class LineSpeaker(object):
    def __init__(
        self,
        role=None,
        debug=False,
        quiet=False,
        speed=150,
        mute=False,
        clear=False,
        scenes=(),
        display_role=False,
    ):
        self.role = role
        if debug:
            LOGGER.setLevel(logging.DEBUG)
        self.quiet = quiet
        self.speed = speed
        LOGGER.debug("Speed = {}".format(speed))
        self.mute = mute
        self.clear = clear
        self.display_role = display_role
        self.scenes = set()
        for scene in scenes:
            for num in mixrange(scene):
                LOGGER.debug("Adding scene {}".format(num))
                self.scenes.add(num)
        LOGGER.debug("Scenes: {}".format(self.scenes))
        self._prev_role = "STAGE DIRECTIONS"
        self._current_scene = 0
        self._voices = {}
        for k, v in VOICES.items():
            try:
                self._voices[k.lower()] = v
            except AttributeError:
                self._voices[k] = v
        if None not in self._voices:
            self._voices[None] = "tom"

        self._rows, self._columns = list(
            map(int, os.popen("stty size", "r").read().split())
        )

    DIALOGUE_RE = re.compile(r"^([A-Z\s_,\'ac&]+):\s*(.*)")

    @property
    def current_scene(self):
        return self._current_scene

    @current_scene.setter
    def current_scene(self, value):
        LOGGER.debug("=== setting current scene to {}".format(value))
        self._current_scene = value

    def next_scene(self):
        self.current_scene += 1

    def perform_line(self, line):
        if self.scenes and self.current_scene not in self.scenes:
            LOGGER.debug(
                "=== skipping (not in scene {}): {}".format(self.current_scene, line)
            )
            return
        LOGGER.debug("=== perform_line({})".format(line))
        matcher = self.DIALOGUE_RE.match(line)
        if matcher:
            role, line = matcher.groups()
            role_to_speak = self.find_role_to_use(role)
            LOGGER.debug("=== {} === {}".format(role, line))
            if line.strip() == "":
                self.speak_a_line(role.lower(), line, role_to_speak)
                self._prev_role = role.upper()
            else:
                for y in re.split(r"(\([^(]*\))", line):
                    y = y.strip()
                    if y != "":
                        if y.startswith("("):
                            self.speak_a_line("stage directions", y)
                        else:
                            self.speak_a_line(role.lower(), y, role_to_speak)
                            self._prev_role = role.upper()
        else:
            self.perform_line("{}: {}".format(self._prev_role, line))

    def list_scenes_and_roles(self, scriptfile):
        print("\nROLES:\n")
        LOGGER.debug(self._voices)
        for role in sorted(
            self._voices.keys(),
            key=lambda x: x if isinstance(x, str) else chr(sys.maxunicode),
        ):
            if role:
                print(
                    "{0}: {1}{2}".format(
                        role.upper(),
                        self._voices[role][0].upper(),
                        self._voices[role][1:].lower(),
                    )
                )
        print("\nSCENES:\n")
        counter = 1
        for line in scriptfile:
            if line.startswith("{scene}"):
                print("{0}: {1}".format(counter, line[7:].strip()))
                counter += 1

    def find_role_to_use(self, role):
        LOGGER.debug("=== find_role_to_use({0})".format(role))
        # deal with multiple roles
        roles = role.split(",")
        roles = [x.lower().strip() for x in roles]
        if self.role in roles and self.role in self._voices:
            LOGGER.debug("=== using {0}".format(self.role))
            return self.role
        else:
            for r in roles:
                if r in self._voices:
                    LOGGER.debug("=== using {0}".format(r))
                    return r
            else:
                LOGGER.debug("=== using {0}".format(None))
                return None

    def speak_a_line(self, role, line, role_to_speak=None):
        if role_to_speak is None:
            role_to_speak = role
        if self.clear:
            subprocess.call(["/usr/bin/clear"])
        if role_to_speak in self._voices:
            voice = self._voices[role_to_speak]
        else:
            voice = self._voices[None]
            line = "{} says: {}".format(role, line)
        sys.stdout.write("\n{}\n".format(role.upper()))
        if role == self.role and not self.mute:
            if self.display_role:
                sys.stdout.write("{}\n".format(textwrap.fill(line, self._columns)))
            while True:
                sys.stdout.flush()
                say_it = readchar.readchar().lower()
                LOGGER.debug(">>>{}<<<".format(say_it))
                if say_it == "\x03":
                    raise KeyboardInterrupt
                elif say_it == "\x04":
                    raise EOFError
                elif say_it == "?":
                    sys.stdout.write(
                        "  Hit H for a hint, Y to read the whole line,\n"
                        "  Ctrl-C or Ctrl-D to exit, or any key to move on to the next line\n"
                    )
                elif say_it == "h":
                    if " " in line:
                        hint, line = re.split(r"\s+", line, 1)
                    else:
                        hint, line = line, None
                    if not self.display_role:
                        sys.stdout.write("{} ".format(hint))
                    self.vocalise(voice, hint, self.mute)
                    if line is None:
                        sys.stdout.write("\n")
                        return
                else:
                    break
        else:
            say_it = "y"
        if not (role == self.role and (self.mute or self.display_role)):
            sys.stdout.write("{}\n".format(textwrap.fill(line, self._columns)))
        if not say_it.lower().startswith("y"):
            return
        self.vocalise(voice, line, mute=(self.mute and role == self.role))

    def vocalise(self, voice, line, mute):
        if self.quiet:
            LOGGER.debug("--- say -v {} {}".format(voice, line))
        else:
            if mute:
                subprocess.call(
                    ["/usr/bin/osascript", "-e", "set volume output muted true"]
                )
                subprocess.call(
                    ["/usr/bin/say", "-v", voice, "-r", "150", "--interactive", line]
                )
                subprocess.call(
                    ["/usr/bin/osascript", "-e", "set volume output muted false"]
                )
            else:
                subprocess.call(
                    [
                        "/usr/bin/say",
                        "-v",
                        voice,
                        "-r",
                        str(self.speed),
                        textwrap.fill(line, self._columns),
                    ]
                )


def interactively_get_args(scriptfile):
    """
    It's too hard to remember all these arguments. Let the program do the heavy lifting.
    """
    print("You are learning {0}".format(scriptfile.name))
    print("")
    role = None
    while not role:
        role = input("Which role are you learning? ")
    args = ["-r", role]
    no_arg_opts = [
        ["Suppress audio output", "-q"],
        ["Produce debugging output", "-d"],
        ["Mute while delivering the role's line", "-m"],
        ["Clear the screen before each line", "-c"],
        ["Always display the role's line", "--display"],
    ]
    for opt in no_arg_opts:
        val = input("{0}? [y|n, default=n] ".format(opt[0])).lower()
        if val and val[0] == "y":
            args.append(opt[1])
    speed = input("Spoken audio speed (wpm)? [default=180]")
    if speed:
        args.extend(["-s", int(speed)])
    print()
    print("I know the following scenes:")
    speaker = LineSpeaker(role)
    speaker.list_scenes_and_roles(scriptfile)
    print()
    print("Which scenes would you like to rehearse?")
    scenes = input(
        "Enter a set of scene numbers, such as 1,2,4-6 [default=all scenes]: "
    )
    if scenes:
        args.extend(["--scene", scenes])
    print()
    print("Thank you.  Next time you could skip this introduction by just running:")
    print(
        "  {0} {1}".format(
            sys.argv[0],
            " ".join(args),
        )
    )
    args.append(scriptfile.name)
    return args


def main():
    parser = argparse.ArgumentParser(description="Learn a script")
    parser.add_argument(
        "-r", "--role", metavar="ROLE", type=str, nargs=1, help="Role you are learning"
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Don't produce any audio output"
    )
    parser.add_argument(
        "-d", "--debug", action="store_true", help="Debugging output on"
    )
    parser.add_argument(
        "-s",
        "--speed",
        metavar="SPEED",
        type=int,
        default=180,
        help="Speed of speech in wpm (default=180)",
    )
    parser.add_argument(
        "-m",
        "--mute",
        action="store_true",
        help="Mute while delivering the role's line, rather than pausing",
    )
    parser.add_argument(
        "-c", "--clear", action="store_true", help="Clear the screen before each line"
    )
    parser.add_argument(
        "-v",
        "--voices",
        type=argparse.FileType("r"),
        nargs=1,
        help="JSON file containing voices",
    )
    parser.add_argument(
        "-S",
        "--scene",
        action="append",
        dest="scenes",
        default=[],
        help="Only read the specified scene numbers",
    )
    parser.add_argument(
        "--display", action="store_true", help="Always display the role's line"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all known roles and all scenes by number and exit",
    )
    parser.add_argument(
        "-x",
        "--no-defaults",
        action="store_true",
        help="Ignore defaults; take all arguments from command line "
        "(NB: your voices definition file must include a definition for 'STAGE DIRECTIONS')",
    )
    parser.add_argument(
        "-i", "--interactive", action="store_true", help="Interactively set options"
    )
    parser.add_argument(
        "scriptfile", type=argparse.FileType("r"), help="File containing the script"
    )
    args = parser.parse_args()
    if args.debug:
        LOGGER.setLevel(logging.DEBUG)
    LOGGER.debug("testing debug")
    global VOICES
    if args.voices:
        if args.no_defaults:
            LOGGER.debug("Ignoring default voices")
            VOICES = {}
        VOICES.update(json.load(args.voices[0]))
    else:
        default_voices = os.path.join(
            os.path.split(args.scriptfile.name)[0], "voices.json"
        )
        if os.path.exists(default_voices):
            print(
                "No voices.json found, but I found one at {0}, which I'm loading".format(
                    default_voices
                )
            )
            VOICES.update(json.load(open(default_voices)))
    if args.interactive:
        args = parser.parse_args(interactively_get_args(args.scriptfile))
    if args.role:
        role = args.role[0].lower()
    else:
        role = "_no_role"
    speaker = LineSpeaker(
        role,
        quiet=args.quiet,
        debug=args.debug,
        speed=args.speed,
        mute=args.mute,
        clear=args.clear,
        scenes=args.scenes,
        # voices=VOICES,
        display_role=args.display,
    )
    if args.list:
        speaker.list_scenes_and_roles(args.scriptfile)
        return
    print("You are learning {}".format(role))
    for line in args.scriptfile:
        line = line.strip()
        if line.startswith("{scene}"):
            speaker.next_scene()
            speaker.perform_line("({})".format(line[7:]))
        elif line != "":
            speaker.perform_line(line)


if __name__ == "__main__":
    main()
