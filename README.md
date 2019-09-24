# BinX86Ext

When building performant code, cpu intrinsics are frequently necessary to maximize the performance of a given program.
This program attempts to identify the necessary ISA extensions to run a given binary program.
Starting with intel x86 instructions a dictionary of instructions and extensions is built from the official intel published materials.
Then a helper program like objdump is run to dissassemble the binary or library and list all used opcodes.
With the completed list of opcodes, a list of necessary ISA extensions is produced.

## Building the ISA extension dictionary

Official Intel documentation such as https://software.intel.com/sites/default/files/managed/a4/60/325383-sdm-vol-2abcd.pdf is mined to produce an official dictionary of x86 instructions and extensions.

## Identifying necessary ISA extensions

The dictionary is then used to identify necessary ISA extensions to run the given binary.
