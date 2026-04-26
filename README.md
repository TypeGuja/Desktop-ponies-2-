because of a better version in Python, this option can be closed, and we switch to Rust (I'm very sorry)
in the Rust version, multiplayer will finally go away (Russia is not in the best position and my connecting server was blocked due to the locks), only the clean version will remain and after the Rust census, the gifs will be redrawn (not immediately)(the configuration format of the personages will be as in the original (my version performed poorly (but it was readable)))





types of updates (letters) - 
m - сomplete modernization.
k - modernizing the in-game part (improving the task code).
f - upgrading the video part of the game.
u - small code updates.
t - Gifct update.                                                                                     ()

build command with nuitka: python -m nuitka --standalone --windows-console-mode=disable --mingw64 --enable-plugin=pyside6 --enable-plugin=tk-inter --include-package=PIL --include-module=PIL.Image --include-module=PIL.ImageTk --include-module=PIL.ImageDraw --include-module=PIL.ImageFont --include-module=psutil --include-module=colorama --enable-plugin=numpy --include-package=pygame --output-filename="DPP2_v2.03.exe" DPP2Launcher.py   
