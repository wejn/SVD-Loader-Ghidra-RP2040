# SVD-Loader for Ghidra (with customization for RP2040)

## Provenance

This SVD-Loader originally comes from [leveldown-security](https://github.com/leveldown-security/SVD-Loader-Ghidra),
and was adjusted by [rpavlik](https://github.com/rpavlik/SVD-Loader-Ghidra).
Unfortunately that pull request is still hanging open as of 2023-02-24.

## Intro

For basic info [read leveldown's blog post](https://leveldown.de/blog/svd-loader/);
for specifics about this fork read
[my blog post](https://wejn.org/2023/02/making-ghidra-svd-loader-play-nice-with-rp2040/).

This version contains adjustments targeted at RP2040, which has rather unique
addition to the memory ranges, see 2.1.2. (Atomic Register Access) on the
[RP2040 datasheet](https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf)
for details.

As well as other useful tweaks:

- Peripheral generation should be idempotent (you can re-run the script to add what's missing)
- Data structures for derived peripherals are re-used
- Data structures for derived RP2040 peripherals are aliased (UART instead of UART0)
- Pointers to structures are auto-added as a type, too

So you get correct references
(instead of [this](https://wejn.org/assets/2023-rp2040-ghidra/pre-refs.png)):

![correct references](https://wejn.org/assets/2023-rp2040-ghidra/post-refs.png)

and working decompile
(instead of [this](https://wejn.org/assets/2023-rp2040-ghidra/pre-decompile.png)):

![working decompile](https://wejn.org/assets/2023-rp2040-ghidra/post-decompile.png)

## Installation

Simply add the checked-out Git repository to your Ghidra-Scripts search paths.

Example:

``` sh
# Assuming Linux & Ghidra installed in `/home/foo/ghidra_10.X.Y_PUBLIC`
cd /home/foo/ghidra_10.X.Y_PUBLIC
cd ./Ghidra/Features/Base/ghidra_scripts/
git clone https://github.com/wejn/SVD-Loader-Ghidra-RP2040
ln -s SVD-Loader-Ghidra-RP2040/cmsis_svd .
ln -s SVD-Loader-Ghidra-RP2040/SVD-Loader.py .
```

## Usage

As described on [the original blog post](https://leveldown.de/blog/svd-loader/):

1. Load a binary file
1. Open it in the code-browser, do not analyze it
1. Run the `SVD-Loader` Script
1. Select an SVD file
1. [Once the script finishes] Analyze the file

## Getting SVDs

- [cmsis-svd contains over 650 SVDs](https://github.com/posborne/cmsis-svd/)
- [Keil Software Packs](https://www.keil.com/pack)
- [RP2040 pico-sdk](https://github.com/raspberrypi/pico-sdk/tree/master/src/rp2040/hardware_regs)

## Credits / authors

The cmsis-svd code is a fork from Posborne's
[cmsis-svd](https://github.com/posborne/cmsis-svd/), ported to work on Ghidra's
Jython. Without this library this script could not exist!

- Thomas Roth (thomas.roth@leveldown.de) :: the original author
- Ryan Pavlik (ryan.pavlik@gmail.com) :: misc fixes 
- Michal Jirků (box@wejn.org) :: RP2040 tweaks

## Licensing

The code in `cmsis_svd/` is licensed under the Apache License v2.0, the same as
the 'upstream' [cmsis-svd](https://github.com/posborne/cmsis-svd/). The
SVD-Loader itself is licensed under GPLv3.
