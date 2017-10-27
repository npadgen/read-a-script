#!/usr/bin/env python

# https://stackoverflow.com/questions/12758591/python-text-to-speech-in-macintosh#12761406

from  AppKit import NSSpeechSynthesizer
import time
import sys


def print_and_say(text):
    words = text.split(' ')
    ve.startSpeakingString_(text)
    while not ve.isSpeaking():
        time.sleep(0.05)
    while len(words) > 0:
        sys.stdout.write(words.pop(0) + ' ')
        sys.stdout.flush()
        ve.pauseSpeakingAtBoundary_(1)
        while ve.isSpeaking():
            time.sleep(0.05)
        ve.continueSpeaking()
        time.sleep(0.05)


if len(sys.argv) < 2:
   text = input('type text to speak> ')
else:
   text = ' '.join(sys.argv[1:])

nssp = NSSpeechSynthesizer

ve = nssp.alloc().init()

for voice in nssp.availableVoices():
   ve.setVoice_(voice)
   print(voice)
#   ve.startSpeakingString_(text)
#
#   while not ve.isSpeaking():
#      time.sleep(0.1)
#
#   while ve.isSpeaking():
#      time.sleep(0.1)
   print_and_say(text)
