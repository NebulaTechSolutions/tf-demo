.syntax unified
.cpu cortex-m7
.thumb

.section .vectors, "a", %progbits
.word _stack_top
.word reset_handler

.section .text.startup, "ax", %progbits
.global reset_handler
.type reset_handler, %function
.thumb_func
reset_handler:
    cpsid i
    ldr r0, =_data_load
    ldr r1, =_data_start
    ldr r2, =_data_end
1:
    cmp r1, r2
    bhs 2f
    ldr r3, [r0], #4
    str r3, [r1], #4
    b 1b
2:
    ldr r1, =_bss_start
    ldr r2, =_bss_end
    movs r3, #0
3:
    cmp r1, r2
    bhs 4f
    str r3, [r1], #4
    b 3b
4:
    b firmware_main
.size reset_handler, . - reset_handler
