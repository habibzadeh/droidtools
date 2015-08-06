#!/usr/bin/env python3
# Original source: https://github.com/chenxiaolong/DualBootPatcher
# Python 2 compatibility
from __future__ import print_function

import binascii
import os
import struct
import sys
import traceback

BOOT_MAGIC = "ANDROID!"
BOOT_MAGIC_SIZE = 8
BOOT_NAME_SIZE = 16
BOOT_ARGS_SIZE = 512

MODE_STANDARD = 1
MODE_DEGAS = 2


def read_padding(f, itemsize, pagesize):
    pagemask = pagesize - 1

    if (itemsize & pagemask) == 0:
        return 0

    count = pagesize - (itemsize & pagemask)

    f.read(count)

    return count


def bytes_to_str(data):
    temp = binascii.hexlify(data).decode("utf-8")
    #return "\\x" + "\\x".join(a + b for a, b in zip(temp[::2], temp[1::2]))
    return "".join(a + b for a, b in zip(temp[::2], temp[1::2]))


show_output = True
use_stdout = False


def print_i(line):
    if show_output:
        if use_stdout:
            print(line)
        else:
            print(line, file=sys.stderr)


def extract(filename, directory, mode = MODE_STANDARD):
    basename = os.path.split(filename)[1]
    f = open(filename, 'rb')

    i = 0
    while i <= 512:
        f.seek(i, os.SEEK_SET)
        temp = f.read(BOOT_MAGIC_SIZE)
        if temp == BOOT_MAGIC.encode("ASCII"):
            # print_i("Found Android header")
            break
        i += 1

    if i > 512:
        raise Exception("Android header not found")

    # Read Android header
    f.seek(0, os.SEEK_SET)

    sformat = '<'
    sformat += str(BOOT_MAGIC_SIZE) + 's'  # magic
    sformat += '10I'                       # kernel_size, kernel_addr,
                                           # ramdisk_size, ramdisk_addr,
                                           # second_size, second_addr,
                                           # tags_addr, page_size,
                                           # dt_size, unused
    sformat += str(BOOT_NAME_SIZE) + 's'   # name
    sformat += str(BOOT_ARGS_SIZE) + 's'   # cmdline
    sformat += str(8 * 4) + 's'            # id (unsigned[8])

    header_size = struct.calcsize(sformat)
    header = f.read(header_size)

    if mode == MODE_DEGAS:
        magic, kernel_size, kernel_addr, \
            ramdisk_size, ramdisk_addr, \
            second_size, second_addr, \
            dt_size, unused, \
            tags_addr, page_size, \
            board, cmdline, ident = struct.unpack(sformat, header)

    ramdisk_offset = ramdisk_addr - kernel_addr + 0x00008000
    tags_offset = tags_addr - kernel_addr + 0x00008000
    second_offset = second_addr - kernel_addr + 0x00008000

    print_i("Android magic found at: 0")
    print_i("BOARD_KERNEL_CMDLINE %s" % cmdline.decode('ASCII').rstrip('\0'))
    print_i("BOARD_KERNEL_BASE %08x" % (kernel_addr - 0x00008000))
    print_i("BOARD_RAMDISK_OFFSET %08x" %  ramdisk_offset)
    print_i("BOARD_SECOND_OFFSET %08x" % second_offset)
    print_i("BOARD_TAGS_OFFSET %08x" % tags_offset)
    print_i("BOARD_PAGE_SIZE %s" % page_size)
    print_i("BOARD_SECOND_SIZE %s" % second_size)
    print_i("BOARD_DT_SIZE %s" % dt_size)


    # cmdline
    out = open(os.path.join(directory, basename + "-cmdline"), 'wb')
    out.write((cmdline.decode('ASCII').rstrip('\0') + '\n').encode('ASCII'))
    out.close()

    # base
    out = open(os.path.join(directory, basename + "-base"), 'wb')
    out.write(('%08x\n' % (kernel_addr - 0x00008000)).encode('ASCII'))
    out.close()

    # ramdisk_offset
    out = open(os.path.join(directory, basename + "-ramdisk_offset"), 'wb')
    out.write(('%08x\n' % ramdisk_offset).encode('ASCII'))
    out.close()

    # second_offset
    out = open(os.path.join(directory, basename + "-second_offset"), 'wb')
    out.write(('%08x\n' % second_offset).encode('ASCII'))
    out.close()

    # tags_offset
    out = open(os.path.join(directory, basename + "-tags_offset"), 'wb')
    out.write(('%08x\n' % tags_offset).encode('ASCII'))
    out.close()

    # page_size
    out = open(os.path.join(directory, basename + "-pagesize"), 'wb')
    out.write(('%d\n' % page_size).encode('ASCII'))
    out.close()

    read_padding(f, header_size, page_size)

    # zImage
    out = open(os.path.join(directory, basename + "-zImage"), 'wb')
    out.write(f.read(kernel_size))
    out.close()

    read_padding(f, kernel_size, page_size)

    # ramdisk
    ramdisk = f.read(ramdisk_size)
    if ramdisk[0] == 0x02 and ramdisk[1] == 0x21:
        out = open(os.path.join(directory, basename + "-ramdisk.lz4"), 'wb')
    else:
        out = open(os.path.join(directory, basename + "-ramdisk.gz"), 'wb')
    out.write(ramdisk)
    out.close()

    read_padding(f, ramdisk_size, page_size)

    # second
    out = open(os.path.join(directory, basename + "-second"), 'wb')
    out.write(f.read(second_size))
    out.close()

    read_padding(f, second_size, page_size)

    # dt
    out = open(os.path.join(directory, basename + "-dt"), 'wb')
    out.write(f.read(dt_size))
    out.close()

    #signature
    out = open(os.path.join(directory, basename + "-signature"), 'wb')
    out.write(f.read(256))
    out.close()

    f.close()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print_i("Usage: %s -i boot.img [-o output_directory]" % sys.argv[0])
        sys.exit(1)

    filename = ""
    directory = ""

    counter = 1
    while counter < len(sys.argv):
        if sys.argv[counter] == "-i":
            filename = sys.argv[counter + 1]
            counter += 2
        elif sys.argv[counter] == "-o":
            directory = sys.argv[counter + 1]
            counter += 2
        else:
            print_i("Unrecognized argument " + sys.argv[counter])
            sys.exit(1)

    if filename == "":
        print_i("No boot image specified")
        sys.exit(1)

    if not os.path.exists(filename):
        print_i(filename + " does not exist")
        sys.exit(1)

    if directory == "":
        directory = os.getcwd()
    elif not os.path.exists(directory):
        os.makedirs(directory)

    try:
        use_stdout = True
        extract(filename, directory)
    except Exception as e:
        use_stdout = False
        print(traceback.format_exc())
        print_i("Failed: " + str(e))