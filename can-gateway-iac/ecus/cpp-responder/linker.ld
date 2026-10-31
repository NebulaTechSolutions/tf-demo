ENTRY(reset_handler)
MEMORY {
    FLASH (rx) : ORIGIN = 0x00400000, LENGTH = 4M
    RAM (rw) : ORIGIN = 0x20400000, LENGTH = 64K
}
_stack_top = ORIGIN(RAM) + LENGTH(RAM);
SECTIONS {
    /* ECUSim's S32K344 boot vector is at flash + 0x400. */
    .boot : { LONG(0); . = ORIGIN(FLASH) + 0x400; KEEP(*(.vectors)) } > FLASH
    .text : { *(.text*) *(.rodata*) } > FLASH
    .ARM.exidx : { *(.ARM.exidx*) } > FLASH
    .data : {
        . = ALIGN(4); _data_start = .;
        *(.data*)
        . = ALIGN(4); _data_end = .;
    } > RAM AT> FLASH
    _data_load = LOADADDR(.data);
    .bss (NOLOAD) : {
        . = ALIGN(4); _bss_start = .;
        *(.bss*) *(COMMON)
        . = ALIGN(4); _bss_end = .;
    } > RAM
    .init_array : { *(.init_array*) } > FLASH
    ASSERT(SIZEOF(.init_array) == 0, "Static constructors are not supported")
    ASSERT(_bss_end <= _stack_top - 4096, "Reserve 4 KiB for the stack")
}
