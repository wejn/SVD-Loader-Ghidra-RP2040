## ###
# -*- coding: utf-8 -*-
##
# Load specified SVD and generate peripheral memory maps & structures, with RP2040 tweaks.
#@author Thomas Roth <thomas.roth@leveldown.de>, Ryan Pavlik <ryan.pavlik@gmail.com>, Michal Jirků <box@wejn.org>
#@category Data
#@keybinding 
#@menupath 
#@toolbar

# More information:
# https://wejn.org/2023/02/making-ghidra-svd-loader-play-nice-with-rp2040/
# License: GPLv3

import sys

from cmsis_svd.parser import SVDParser
from ghidra.program.model.data import Structure, StructureDataType, PointerDataType, UnsignedIntegerDataType, DataTypeConflictHandler
from ghidra.program.model.data import UnsignedShortDataType, ByteDataType, UnsignedLongLongDataType
from ghidra.program.model.mem import MemoryBlockType
from ghidra.program.model.address import AddressFactory
from ghidra.program.model.symbol import SourceType
from ghidra.program.model.mem import MemoryConflictException

class MemoryRegion:
	def __init__(self, name, start, end, name_parts=None):
		self.start = start
		self.end = end
		if name_parts:
			self.name_parts = name_parts
		else:
			self.name_parts = [name]

		assert(self.start < self.end)

	@property
	def name(self):
		return "_".join(self.name_parts)

	def length(self):
		return self.end - self.start

	def __lt__(self, other):
		return self.start < other.start

	def combine_with(self, other):
		return MemoryRegion(None,
			min(self.start, other.start),
			max(self.end, other.end),
			self.name_parts + other.name_parts)

	def combine_from(self, other):
		self.start = min(self.start, other.start)
		self.end = max(self.end, other.end)
		self.name_parts.extend(other.name_parts)
	
	def overlaps(self, other):
		if other.end < self.start:
			return False
		if self.end < other.start:
			return False
		return True
	
	def __str__(self):
		return "{}({}:{})".format(self.name, hex(self.start), hex(self.end))

def reduce_memory_regions(regions):
	regions.sort()
	print("Original regions: " + ", ".join(str(x) for x in regions))
	result = [regions[0]]
	for region in regions[1:]:
		if region.overlaps(result[-1]):
			result[-1].combine_from(region)
		else:
			result.append(region)

	print("Reduced regions: " + ", ".join(str(x) for x in result))
	return result

def calculate_peripheral_size(peripheral, default_register_size):
	size = 0
	for register in peripheral.registers:
		register_size = default_register_size if not register._size else register._size
		size = max(size, register.address_offset + register_size/8)
	return size


svd_file = askFile("Choose SVD file", "Load SVD File")

print("Loading SVD file...")
parser = SVDParser.for_xml_file(str(svd_file))
print("\tDone!")

# CM0, CM4, etc
cpu_type = parser.get_device().cpu.name
# little/big
cpu_endian = parser.get_device().cpu.endian

# RP2040 has "width", not "size", and da0c2a18 commit promised 32bit default anyway
default_register_size = parser.get_device().size or parser.get_device().width or 32

# Not all SVDs contain these fields
if cpu_type and not cpu_type.startswith("CM"):
	print("Currently only Cortex-M CPUs are supported, so this might not work...")
	print("Supplied CPU type was: " + cpu_type)

if cpu_endian and cpu_endian != "little":
	print("Currently only little endian CPUs are supported.")
	print("Supplied CPU endian was: " + cpu_endian)
	sys.exit(1)

address_extras = {}
address_extras_comments = {}
address_extras_cond = lambda addr: False
peripheral_name_aliases = {}
# rp2040 tweaks, see section 2.1.2 (Atomic Register Access) in RP2040 Datasheet
# https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf
if parser.get_device().name == "RP2040":
	print("RP2040 detected, tweaks enabled.")
	address_extras_cond = lambda addr: addr >= 0x40000000 and addr < 0xd0000000
	address_extras = {'xor': 0x1000, 'set': 0x2000, 'clr': 0x3000}
	address_extras_comments = {
		'xor': 'Note: atomic xor on write',
		'set': 'Note: atomic bitmask set on write',
		'clr': 'Note: atomic bitmask clear on write',
	}
	peripheral_name_aliases = {
		'PLL_SYS': 'PLL',
		'UART0': 'UART',
		'SPI0': 'SPI',
		'I2C0': 'I2C',
		'PIO0': 'PIO',
	}

# Get things we need
listing = currentProgram.getListing()
symtbl = currentProgram.getSymbolTable()
dtm = currentProgram.getDataTypeManager()
space = currentProgram.getAddressFactory().getDefaultAddressSpace()

namespace = symtbl.getNamespace("Peripherals", None)
if not namespace:
	namespace = currentProgram.getSymbolTable().createNameSpace(None, "Peripherals", SourceType.ANALYSIS)

peripherals = parser.get_device().peripherals

print("Generating memory regions...")
# First, we need to generate a list of memory regions.
# This is because some SVD files have overlapping peripherals...
memory_regions = []
for peripheral in peripherals:
	start = peripheral.base_address
	length = peripheral.address_block.offset + peripheral.address_block.size
	end = peripheral.base_address + length

	memory_regions.append(MemoryRegion(peripheral.name, start, end))
memory_regions = reduce_memory_regions(memory_regions)

print("Generating memory blocks...")
# Create memory blocks:
for r in memory_regions:
	print("\t" + str(r))

	def add_block(name, start, length, comment):
		try:
			addr = space.getAddress(start)
			t = currentProgram.memory.createUninitializedBlock(name, addr, length, False)
			t.setRead(True)
			t.setWrite(True)
			t.setExecute(False)
			t.setVolatile(True)
			t.setComment(comment)
		except ghidra.program.model.mem.MemoryConflictException as e:
			print("\tFailed to generate due to conflict in memory block for: " + name + ", " + str(e))
		except Exception as e:
			print("\tFailed to generate memory block for: " + name + ", " + str(e))

	length = r.length()

	add_block(r.name, r.start, length, "")

	if address_extras_cond(r.start):
		for k, v in address_extras.items():
			add_block(r.name + '_' + k, r.start + v, length, address_extras_comments[k] or "")

print("\tDone!")

print("Generating peripherals...")
peripherals_cache = {}
for peripheral in peripherals:
	print("\t" + peripheral.name)

	if(len(peripheral.registers) == 0):
		print("\t\tNo registers.")
		continue

	# try:
	# Iterage registers to get size of peripheral
	# Most SVDs have an address-block that specifies the size, but
	# they are often far too large, leading to issues with overlaps.
	length = calculate_peripheral_size(peripheral, default_register_size)

	def gen_struct(name, peripheral, start, length):
		peripheral_start = start
		peripheral_end = peripheral_start + length

		df = peripheral.get_derived_from()
		if df and df.name in peripherals_cache:
			# Re-use structure for the peripheral
			peripheral_struct = peripherals_cache[df.name]
			print("\t\t{}:{} [{}] (reusing {})".format(hex(peripheral_start), hex(peripheral_end), str(name), str(df.name)))
		else:
			# Generate structure for the peripheral
			peripheral_struct = StructureDataType(peripheral_name_aliases.get(peripheral.name, peripheral.name), length)

			print("\t\t{}:{} [{}]".format(hex(peripheral_start), hex(peripheral_end), str(name)))

			if peripheral.get_derived_from():
				print(peripheral.name + " is DF: " + str(peripheral.get_derived_from().name))

			for register in peripheral.registers:
				register_size = default_register_size if not register._size else register._size

				r_type = UnsignedIntegerDataType()
				rs = register_size / 8
				if rs == 1:
					r_type = ByteDataType()
				elif rs == 2:
					r_type = UnsignedShortDataType()
				elif rs == 8:
					r_type = UnsignedLongLongDataType()

				#print("\t\t\t{}({}:{})".format(register.name, hex(register.address_offset), hex(register.address_offset + register_size/8)))
				peripheral_struct.replaceAtOffset(register.address_offset, r_type, register_size/8, register.name, register.description)

		peripherals_cache[peripheral.name] = peripheral_struct

		try:
			addr = space.getAddress(peripheral_start)
			dt = dtm.addDataType(peripheral_struct, DataTypeConflictHandler.REPLACE_HANDLER)
			dtm.addDataType(PointerDataType(dt), DataTypeConflictHandler.REPLACE_HANDLER)
			symtbl.createLabel(addr, name, namespace, SourceType.USER_DEFINED)
			listing.createData(addr, peripheral_struct, False)
		except ghidra.program.model.util.CodeUnitInsertionException as e:
			print("\t\tFailed to generate peripheral (ins) " + peripheral.name + ", " + str(e))
		except Exception as e:
			print("\t\tFailed to generate peripheral " + peripheral.name + ", " + str(e))

	gen_struct(peripheral.name, peripheral, peripheral.base_address, length)

	if address_extras_cond(peripheral.base_address):
		for k, v in address_extras.items():
			gen_struct(peripheral.name + '_' + k, peripheral, peripheral.base_address + v, length)
