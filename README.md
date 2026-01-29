types of updates (letters) - 
m - сomplete modernization.
k - modernizing the in-game part (improving the task code).
f - upgrading the video part of the game.
u - small code updates.
t - Gifct update.

in the near future, the ASNP generation will be created (several drawings in one class, as well as associations)
This Python project was created by accident, the reasons for its appearance:
1 rewrite the game engine to make it easier to understand.
2 Adding characters from famous bloggers and those who want to get into the game (please add your wishes in the suggestions).
3 The idea of multiplayer with server monitor capture (the idea was that my server's screen would be captured and the players 
on it could do whatever they wanted, but in practice it turned out to be more difficult to do than I thought)

build command with nuitka: python -m nuitka --standalone --windows-console-mode=disable --mingw64 --enable-plugin=pyside6 --enable-plugin=tk-inter --include-package=PIL --include-module=PIL.Image --include-module=PIL.ImageTk --include-module=PIL.ImageDraw --include-module=PIL.ImageFont --include-module=psutil --include-module=colorama --enable-plugin=numpy --include-package=pygame --output-filename="DPP2_v2.03.exe" DPP2Launcher.py   