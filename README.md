# Vertex

Vertex is a Pascal-inspired programming language that compiles to modern C++. This repository contains:

- **vertexc**: the Vertex compiler
- **VCL (Vertex Component Library)**: a Win32 GUI library written in Vertex
- **Vertex IDE**: a visual form designer and code editor
- **Examples**: sample Vertex programs

Vertex combines clean Pascal-like syntax with native Windows GUI development through a C++ backend.

---

## Features

### Language
- Pascal-inspired structure: `Enter` / `Exit`, `Run` / `Stop`
- Procedures and functions
- Records and classes
- Arrays and pointers
- `Asm` blocks for direct C++ injection

### Compiler (vertexc)
- Lexical analysis
- Parsing into an abstract syntax tree
- C++17 code generation
- Import support for `.vtx` modules and system headers

### VCL (Vertex Component Library)
- `Window`, `Button`, `Edit`, `Label`
- `Memo`, `CheckBox`, `Radio`, `ListBox`, `ComboBox`, `GroupBox`, `Panel`
- Colors: `ColorRGB`, `SetFormColor`, `SetBackColor`, `SetCtrlTextColor`
- Events: `OnClick`
- Serial communication: `ComOpen`, `ComClose`, `ComWrite`, `ComRead`, `ComBytesAvailable`

### Vertex IDE
- Code editor
- Drag and drop form designer
- Component palette
- Property editor
- Two-way code and designer sync
- Compile and run workflow
- Themes: dark, light, monokai

---

## Requirements

- Windows 10 or later
- MSYS2 with UCRT64 toolchain (gcc, g++)
- Python 3.10 or later
- Python package: Pillow

---

## Installation

### 1. Install MSYS2 and the C++ toolchain

1. Download MSYS2 from: https://www.msys2.org/
2. Install it (default path recommended): `C:\msys64`
3. Open **MSYS2 UCRT64** from the Start menu.
4. Update and install packages:

```bash
pacman -Syu
```

Close the terminal if it asks you to, reopen MSYS2 UCRT64, then run:

```bash
pacman -Syu
pacman -S mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-gdb mingw-w64-ucrt-x86_64-make
```

5. Add MSYS2 to your PATH:
   · Open System Properties → Environment Variables
   · Under User variables or System variables, select Path
   · Click Edit → New
   · Add: C:\msys64\ucrt64\bin
   · Click OK on all dialogs
   · Close and reopen any open terminals
6. Verify installation:

```bash
gcc --version
g++ --version
```

---

2. Install Python 3

1. Download Python 3.10 or later from: https://www.python.org/downloads/
2. Run the installer and check: Add python.exe to PATH
3. Verify installation:

```bash
python --version
pip --version
```

4. Install Pillow:

```bash
pip install pillow
```

---

3. Get the project

Clone the repository:

```bash
git clone https://github.com/Liams1982/Vertex_IDE.git
cd Vertex_IDE
```

---

4. Build the Vertex compiler

From the project root folder:

```bash
gcc -O2 -std=c99 vertexc.c -o vertexc.exe
```

If successful, you will have vertexc.exe in the project folder.

---

Compiling Vertex Programs

Console example

```bash
vertexc.exe examples\ConsoleCalc.vtx
g++ -O2 -std=c++17 output.cpp -o ConsoleCalc.exe
ConsoleCalc.exe
```

GUI example

```bash
vertexc.exe examples\Calculator.vtx
g++ -O2 -std=c++17 output.cpp -o Calculator.exe -mwindows -static -static-libgcc -static-libstdc++ -luser32 -lgdi32 -lcomdlg32 -lwinmm -ladvapi32
Calculator.exe
```

Using the build helper

```bash
python vertex_build.py examples\Calculator.vtx --mode gui --vertexc vertexc.exe --gpp g++
```

---

Running the IDE

```bash
python vertex_ide.py
```

In the IDE Settings dialog, set:

· vertexc: full path to vertexc.exe
· g++: full path to g++.exe (e.g., C:\msys64\ucrt64\bin\g++.exe)
· Output: your project folder

Then:

· Open or create a .vtx file
· Use the Form Designer to place controls
· Click Generate Code
· Click Compile
· Click Run

---

Minimal Example

```pascal
Import "vcl.vtx";

Enter Hello;

Var btn: HWND;

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
```

---

ComPort Example

```pascal
Import "vcl.vtx";

Enter ComDemo;

Var hPort: Integer;
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
```

Change COM3 to the port used by your device.

---

Common Problems

gcc or g++ is not recognized

· Confirm MSYS2 is installed and C:\msys64\ucrt64\bin is in your PATH
· Close and reopen your terminal
· Test again: g++ --version

python is not recognized

· Reinstall Python and enable Add python.exe to PATH
· Or use: py --version

Import "vcl.vtx" fails

· Run the compiler from the folder that contains vcl.vtx
· Or copy vcl.vtx next to your .vtx source file

GUI program compiles but fails at link time

Use the full GUI link command:

```bash
g++ -O2 -std=c++17 output.cpp -o App.exe -mwindows -static -static-libgcc -static-libstdc++ -luser32 -lgdi32 -lcomdlg32 -lwinmm -ladvapi32
```

IDE opens but images or logo fail

Install Pillow:

```bash
pip install pillow
```

---

Project Layout

```
Vertex_IDE/
├── vertexc.c
├── vertexc.exe
├── vcl.vtx
├── vertex_ide.py
├── vertex_build.py
├── documentation.pdf
├── examples/
├── README.md
└── LICENSE
```

---

Contributing

Contributions are welcome.

1. Fork the repository
2. Create a branch
3. Make a focused change
4. Rebuild and test
5. Open a pull request

Test checklist before a pull request:

· Build compiler: gcc -O2 -std=c99 vertexc.c -o vertexc.exe
· Compile one console example
· Compile one GUI example
· Open the IDE and verify: form designer loads, generate code works, compile works

Good contribution areas:

· Compiler error messages
· VCL controls and helpers
· IDE designer performance and usability
· Examples
· Documentation

---

License

This project is released under the MIT License. See the LICENSE file for details.

Author: Smail Lotmani
Embedded Systems Engineer
LinkedIn: https://www.linkedin.com/in/smaillotmani

---

Credits

Built as a personal language and tooling project by Smail Lotmani, with assistance from free AI tools for implementation, debugging, and documentation.
