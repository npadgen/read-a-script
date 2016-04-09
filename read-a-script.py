#!/usr/local/bin/python

import os
import re
import sys
import fileinput
import subprocess
import argparse
import readchar
import textwrap
import json

VOICES = {
    # Spring and Port Wine
    'rafe': 'tom',
    'arthur': 'lee',
    'harold': 'daniel',
    'wilfred': 'oliver',
    'daisy': 'fiona',
    'florence': 'kate',
    'hilda': 'serena',
    'betsy jane': 'karen',
    None: 'tom',
    'stage directions': 'moira',
    'all': 'daniel',
    # Joining The Club
    'tom': 'tom',
    'jenny': 'karen',
    # The Pigeon with the Silver Foot
    'waiter': 'luca',
    'mary': 'kate',
    'joanna': 'serena',
    'bianca': 'karen',
    'lover': 'lee',
    'customer': 'alice',
    'beggar': 'alice',
    'single female voice': 'allison',
    }

class LineSpeaker(object):

    def __init__(self, role=None, debug=False, quiet=False, speed=150, mute=False, clear=False, scenes=[], voices={}):
        self.role = role
        self.debug = debug
        self.quiet = quiet
        self.speed = speed
        if self.debug:
            print "Speed = {}".format(speed)
        self.mute = mute
        self.clear = clear
        self.scenes = [int(scene) for scene in scenes]
        self._prev_role = 'STAGE DIRECTIONS'
        self._current_scene = 0
        self._voices = {}
        for k, v in VOICES.iteritems():
            try:
                self._voices[k.lower()] = v
            except AttributeError:
                self._voices[k] = v
        if not self._voices.has_key(None):
            self._voices[None] = 'tom'
        
        self._rows, self._columns = map(int, os.popen('stty size', 'r').read().split())
        
    DIALOGUE_RE = re.compile(r'^([A-Z\s_&]+):\s*(.*)')
    
    @property
    def current_scene(self):
        return self._current_scene
    @current_scene.setter
    def current_scene(self, value):
        if self.debug:
            print "=== setting current scene to {}".format(value)
        self._current_scene = value
            
    def next_scene(self):
        self.current_scene += 1

    def perform_line(self, line):
        if self.scenes and self.current_scene not in self.scenes:
            if self.debug:
                print "=== skipping (not in scene {}): {}".format(self.current_scene, line)
            return
        if self.debug:
            print "=== perform_line({})".format(line)
        matcher = self.DIALOGUE_RE.match(line)
        if matcher:
            role, line = matcher.groups()
            if self.debug:
                print "=== {} === {}".format(role, line)
            if line.strip() == "":
                self.speak_a_line(role.lower(), line)
                self._prev_role = role.upper()
            else:
                for y in re.split(r'(\([^\(]*\))', line):
                    y = y.strip()
                    if y != '':
                        if y.startswith('('):
                            self.speak_a_line('stage directions', y)
                        else:
                            self.speak_a_line(role.lower(), y)
                            self._prev_role = role.upper()
        else:
            self.perform_line('{}: {}'.format(self._prev_role, line))
            
    def list_scenes_and_roles(self, scriptfile):
        print "\nROLES:\n"
        for role in sorted(self._voices.keys()):
            if role:
                print "{0}: {1}{2}".format(
                    role.upper(),
                    self._voices[role][0].upper(),
                    self._voices[role][1:].lower(),
                )
        print "\nSCENES:\n"
        counter = 1
        for line in scriptfile:
            if line.startswith('{scene}'):
                print "{0}: {1}".format(counter, line[7:].strip())
                counter += 1

    def speak_a_line(self, role, line):
        try:
            voice = self._voices[role.lower()]
        except KeyError:
            voice = self._voices[None]
            line = '{} says: {}'.format(role, line)
        if self.clear:
            subprocess.call(['/usr/bin/clear'])
        sys.stdout.write('\n{}\n'.format(role.upper()))
        if role == self.role and not self.mute:
            while True:
                sys.stdout.flush()
                say_it = readchar.readchar().lower()
                if self.debug:
                    print ">>>{}<<<".format(say_it)
                if say_it == '\x03':
                    raise KeyboardInterrupt
                elif say_it == '\x04':
                    raise EOFError
                elif say_it == '?':
                    sys.stdout.write('  Hit H for a hint, Y to read the whole line,\n  Ctrl-C or Ctrl-D to exit, or any key to move on to the next line\n')
                elif say_it == 'h':
                    if ' ' in line:
                        hint, line = re.split(r'\s+', line, 1)
                    else:
                        hint, line = line, None
                    sys.stdout.write('{} '.format(hint))
                    self.vocalise(voice, hint, self.mute)
                    if line is None:
                        sys.stdout.write('\n')
                        return
                else:
                    break
        else:
            say_it = 'y'
        if not (role == self.role and self.mute):
            sys.stdout.write('{}\n'.format(textwrap.fill(line, self._columns)))
        if not say_it.lower().startswith('y'):
            return
        self.vocalise(voice, line, mute=(self.mute and role==self.role))
            
    def vocalise(self, voice, line, mute):
        if self.quiet:
            if self.debug:
                print "--- say -v {} {}".format(voice, line)
        else:
            if mute:
                subprocess.call(['/usr/bin/osascript', '-e', 'set volume output muted true'])
                subprocess.call (['/usr/bin/say',
                                 '-v', voice,
                                 '-r', "150",
                                 '--interactive',
                                 line])
                subprocess.call(['/usr/bin/osascript', '-e', 'set volume output muted false'])
            else:
                subprocess.call (['/usr/bin/say',
                                 '-v', voice,
                                 '-r', str(self.speed),
                                 #'--interactive=green',
                                 textwrap.fill(line, self._columns)])
    
def main():
    parser = argparse.ArgumentParser(description='Learn a script')
    parser.add_argument('-r', '--role', metavar='ROLE',
                        type=str,
                        nargs=1,
                        help='Role you are learning')
    parser.add_argument('-q', '--quiet',
                        action='store_true',
                        help="Don't produce any audio output")
    parser.add_argument('-d', '--debug',
                        action='store_true',
                        help="Debugging output on")
    parser.add_argument('-s', '--speed', metavar='SPEED',
                        type=int,
                        default=150,
                        help="Speed of speech in wpm (default=150)")
    parser.add_argument('-m', '--mute',
                        action='store_true',
                        help="Mute while delivering the role's line, rather than pausing")
    parser.add_argument('-c', '--clear',
                        action="store_true",
                        help="Clear the screen before each line")
    parser.add_argument('-v', '--voices',
                        type=argparse.FileType('r'),
                        nargs=1,
                        help='JSON file containing voices')
    parser.add_argument('-S', '--scene',
                        action='append',
                        dest='scenes',
                        default=[],
                        help='Only read the specified scene numbers'                        
    )
    parser.add_argument('--list',
                        action="store_true",
                        help="List all known roles and all scenes by number and exit")
    parser.add_argument('-x', '--no-defaults',
                        action="store_true",
                        help="Ignore defaults; take all arguments from command line (NB: your voices definition file will need to include a definition for 'STAGE DIRECTIONS')")
    parser.add_argument('scriptfile',
                        type=argparse.FileType('r'),
                        help="File containing the script")
    args = parser.parse_args()
    if args.role:
        role = args.role[0].lower()
    else:
        role = '_no_role'
    if args.voices:
        global VOICES
        if args.no_defaults:
            if args.debug: print "Ignoring default voices"
            VOICES = {}
        VOICES.update(json.load(args.voices[0]))
    speaker = LineSpeaker(role, quiet=args.quiet, debug=args.debug, speed=args.speed, mute=args.mute, clear=args.clear, scenes=args.scenes, voices=VOICES)
    if args.list:
        speaker.list_scenes_and_roles(args.scriptfile)
        return
    print "You are learning {}".format(role)
    for line in args.scriptfile:
        line = line.strip()
        if line.startswith('{scene}'):
            speaker.next_scene()
            speaker.perform_line('({})'.format(line[7:]))
        elif line != '':
            speaker.perform_line(line)

if __name__ == '__main__':
    main()
