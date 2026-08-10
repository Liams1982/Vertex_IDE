Vertex is a Pascal-inspired programming language that compiles to modern C++.
This repository contains:

vertexc: the Vertex compiler

VCL (Vertex Component Library): a Win32 GUI library written in Vertex

Vertex IDE: a visual form designer and code editor

Examples: sample Vertex programs

Vertex combines clean Pascal-like syntax with native Windows GUI development through a C++ backend.

Features
Language
Pascal-inspired structure: Enter / Exit, Run / Stop

Procedures and functions

Records and classes

Arrays and pointers

Asm blocks for direct C++ injection

Compiler (vertexc)
Lexical analysis

Parsing into an abstract syntax tree

C++17 code generation

Import support for .vtx modules and system headers

VCL (Vertex Component Library)
Window, Button, Edit, Label

Memo, CheckBox, Radio, ListBox, ComboBox, GroupBox, Panel

Colors: ColorRGB, SetFormColor, SetBackColor, SetCtrlTextColor

Events: OnClick

Serial communication: ComOpen, ComClose, ComWrite, ComRead, ComBytesAvailable

Vertex IDE
Code editor

Drag and drop form designer

Component palette

Property editor

Two-way code and designer sync

Compile and run workflow

Themes: dark, light, monokai

Requirements
Windows 10 or later

MSYS2 with UCRT64 toolchain (gcc, g++)

Python 3.10 or later

Python package: Pillow

1. Install MSYS2 and the C++ toolchain
Download and install
Download MSYS2 from: https://www.msys2.org/

Install it (default path is recommended):

C:\msys64

Open MSYS2 UCRT64 from the Start menu.

Update and install packages (MSYS2 UCRT64 terminal)
Bashpacman -Syu
Close the terminal if it asks you to, reopen MSYS2 UCRT64, then run:
Bashpacman -Syu
pacman -S mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-gdb mingw-w64-ucrt-x86_64-make
Add MSYS2 to PATH
Add this folder to your Windows PATH:
textC:\msys64\ucrt64\bin
PATH in Windows GUI

Start menu -> search Environment Variables
Open Edit the system environment variables
Click Environment Variables
Under User variables or System variables, select Path
Click Edit
Click New
Add:

textC:\msys64\ucrt64\bin

Click OK on all dialogs
Close and reopen any open terminals

Verify in Command Prompt (cmd)
batgcc --version
g++ --version
Verify in PowerShell
PowerShellgcc --version
g++ --version
Verify in MSYS2 UCRT64
Bashgcc --version
g++ --version
You should see version output for both gcc and g++.

2. Install Python 3
Download Python 3.10 or later from: https://www.python.org/downloads/
Run the installer
Enable:
Add python.exe to PATH
Install pip

Finish installation

Verify in Command Prompt (cmd)
batpython --version
pip --version
Verify in PowerShell
PowerShellpython --version
pip --version
Install required Python package
Command Prompt (cmd)
batpip install pillow
PowerShell
PowerShellpip install pillow
If python is not recognized
Try:
batpy --version
py -m pip install pillow
or:
PowerShellpy --version
py -m pip install pillow

3. Get the project
Option A: clone with Git
Command Prompt (cmd)
batgit clone https://github.com/YOUR_USERNAME/vertex-lang.git
cd vertex-lang
PowerShell
PowerShellgit clone https://github.com/YOUR_USERNAME/vertex-lang.git
cd vertex-lang
MSYS2 UCRT64
Bashgit clone https://github.com/YOUR_USERNAME/vertex-lang.git
cd vertex-lang
Option B: download ZIP

Download the repository ZIP from GitHub
Extract it
Open a terminal in the extracted folder

4. Build the Vertex compiler ()
From the project root folder.
Command Prompt (cmd)
batgcc -O2 -std=c99 vertexc.c -o vertexc.exe
dir vertexc.exe
PowerShell
PowerShellgcc -O2 -std=c99 vertexc.c -o vertexc.exe
Get-Item .\vertexc.exe
MSYS2 UCRT64
Bashgcc -O2 -std=c99 vertexc.c -o vertexc.exe
ls -l vertexc.exe
If successful, you will have vertexc.exe in the project folder.

5. Compile a Vertex program manually
Keep in the same working directory when your program uses:
textImport "vcl.vtx";

5.1 Console example
Command Prompt (cmd)
batvertexc.exe examples\ConsoleCalc.vtx
g++ -O2 -std=c++17 output.cpp -o ConsoleCalc.exe
ConsoleCalc.exe
PowerShell
PowerShell.\vertexc.exe .\examples\ConsoleCalc.vtx
g++ -O2 -std=c++17 .\output.cpp -o .\ConsoleCalc.exe
.\ConsoleCalc.exe
MSYS2 UCRT64
Bash./vertexc.exe examples/ConsoleCalc.vtx
g++ -O2 -std=c++17 output.cpp -o ConsoleCalc.exe
./ConsoleCalc.exe

5.2 GUI example
Command Prompt (cmd)
batvertexc.exe examples\Calculator.vtx
g++ -O2 -std=c++17 output.cpp -o Calculator.exe -mwindows -static -static-libgcc -static-libstdc++ -luser32 -lgdi32 -lcomdlg32 -lwinmm -ladvapi32
Calculator.exe
PowerShell
PowerShell.\vertexc.exe .\examples\Calculator.vtx
g++ -O2 -std=c++17 .\output.cpp -o .\Calculator.exe -mwindows -static -static-libgcc -static-libstdc++ -luser32 -lgdi32 -lcomdlg32 -lwinmm -ladvapi32
.\Calculator.exe
MSYS2 UCRT64
Bash./vertexc.exe examples/Calculator.vtx
g++ -O2 -std=c++17 output.cpp -o Calculator.exe -mwindows -static -static-libgcc -static-libstdc++ -luser32 -lgdi32 -lcomdlg32 -lwinmm -ladvapi32
./Calculator.exe
Important GUI flags

-mwindows: Windows GUI subsystem
-luser32 -lgdi32 ...: Win32 libraries required by VCL

6. Compile using
is the helper used by the IDE and can also be run from a terminal.
Command Prompt (cmd)
batpython vertex_build.py examples\Calculator.vtx --mode gui --vertexc vertexc.exe --gpp g++
PowerShell
PowerShellpython .\vertex_build.py .\examples\Calculator.vtx --mode gui --vertexc .\vertexc.exe --gpp g++
MSYS2 UCRT64
Bashpython vertex_build.py examples/Calculator.vtx --mode gui --vertexc ./vertexc.exe --gpp g++
Useful arguments

--mode auto
--mode gui
--mode console
--output-dir <path>
--vertexc <path-to-vertexc>
--gpp <path-to-g++>

Example with full paths (cmd):
batpython vertex_build.py "C:\path\to\project\examples\Calculator.vtx" --mode gui --output-dir "C:\path\to\project" --vertexc "C:\path\to\project\vertexc.exe" --gpp "C:\msys64\ucrt64\bin\g++.exe"
Example with full paths (PowerShell):
PowerShellpython .\vertex_build.py "C:\path\to\project\examples\Calculator.vtx" --mode gui --output-dir "C:\path\to\project" --vertexc "C:\path\to\project\vertexc.exe" --gpp "C:\msys64\ucrt64\bin\g++.exe"

7. Run the IDE
Command Prompt (cmd)
batpython vertex_ide.py
PowerShell
PowerShellpython .\vertex_ide.py
MSYS2 UCRT64
Bashpython vertex_ide.py
IDE settings
In the IDE Settings dialog, set:

vertexc: full path to vertexc.exe
Example: C:\path\to\project\vertexc.exe

g++: full path to g++
Example: C:\msys64\ucrt64\bin\g++.exe

Output: your project folder

Then:

Open or create a .vtx file
Use Form Designer to place controls
Click Generate Code
Click Compile
Click Run

8. Minimal language example
textImport "vcl.vtx";

Enter Hello;

Var
btn: HWND;

Proc OnBtn(h: HWND);
Run
ShowMessage("Hello from Vertex", "Greeting");
Stop;

Run
Window(400, 200, 100, 100);
SetWindowTitle("Hello");
btn <- Button(MainWindow, 120, 30, 140, 80);
SetText(btn, "Click me");
OnClick(@OnBtn);
RunApp();
Stop
Exit.
Compile it as a GUI program using the commands in section 5.2.

9. ComPort example
textImport "vcl.vtx";

Enter ComDemo;

Var
hPort: Integer;
n: Integer;
data: String;

Run
hPort <- ComOpen("COM3", 9600);
If hPort <> 0 Then
Run
n <- ComWrite(hPort, "AT");
data <- ComRead(hPort, 64);
ComClose(hPort);
Stop;
Stop
Exit.
Change COM3 to the port used by your device.

10. Common problems and fixes
gcc or g++ is not recognized

Confirm MSYS2 is installed
Confirm this is in PATH:

textC:\msys64\ucrt64\bin

Close and reopen the terminal
Test again:

batg++ --version
python is not recognized

Reinstall Python and enable Add python.exe to PATH
Or use:

batpy --version
Import "vcl.vtx" fails

Run the compiler from the folder that contains
Or copy next to your .vtx source file

GUI program compiles but fails at link time
Use the full GUI link command:
batg++ -O2 -std=c++17 output.cpp -o App.exe -mwindows -static -static-libgcc -static-libstdc++ -luser32 -lgdi32 -lcomdlg32 -lwinmm -ladvapi32
IDE opens but images or logo fail
Install Pillow:
batpip install pillow
Permission or path issues with spaces
Prefer paths without spaces, or quote them:
batpython vertex_build.py "C:\path with spaces\app.vtx" --mode gui --vertexc "C:\path with spaces\vertexc.exe" --gpp "C:\msys64\ucrt64\bin\g++.exe"

11. Project layout
textVertex_IDE/
vertexc.c
vertexc.exe
vcl.vtx
vertex_ide.py
vertex_build.py
documentation.pdf
examples/
README.md
LICENSE

12. Contributing
Contributions are welcome.
Suggested workflow

Fork the repository
Create a branch
Make a focused change
Rebuild and test
Open a pull request

Test checklist before a pull request

Build compiler:

batgcc -O2 -std=c99 vertexc.c -o vertexc.exe

Compile one console example
Compile one GUI example
Open the IDE and verify:
form designer loads
generate code works
compile works

Good contribution areas

compiler error messages
VCL controls and helpers
IDE designer performance and usability
examples
documentation

Contribution rules

Keep changes focused
Do not break existing examples without updating them
Prefer clear readable code
Avoid committing temporary files such as local unless intentional

13. License
This project is released under the MIT License.
See the LICENSE file for details.
Author: Smail Lotmani
Embedded Systems Engineer
LinkedIn: https://www.linkedin.com/in/smaillotmani

14. Credits
Built as a personal language and tooling project by Smail Lotmani, with assistance from free AI tools for implementation, debugging,
and documentation.

