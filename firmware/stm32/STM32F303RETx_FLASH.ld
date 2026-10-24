/* STM32F303RETx_FLASH.ld — linker script for the Nucleo-F303RE build.
 *
 * Written for this project rather than copied: ST's SW4STM32 template carries
 * an Ac6 notice that forbids redistribution. The section and symbol names are
 * the ones ST's startup_stm32f303xe.s expects (_sidata, _sdata, _edata,
 * _sbss, _ebss, _estack).
 *
 * 512 KB flash, 64 KB SRAM, 16 KB CCM RAM (RM0316). CCM is declared but
 * unused: nothing is placed there, and the startup code does not initialise it.
 *
 * The array and unwind sections are marked READONLY: they are writable in the
 * ELF, which otherwise makes the flash segment RWX and draws a linker warning.
 */

ENTRY(Reset_Handler)

_estack = ORIGIN(RAM) + LENGTH(RAM);

/* Same sizes as the .ioc (ProjectManager.HeapSize / StackSize). The firmware
 * does not allocate; the heap is there for newlib-nano. */
_Min_Heap_Size  = 0x200;
_Min_Stack_Size = 0x800;

MEMORY
{
  FLASH  (rx)  : ORIGIN = 0x08000000, LENGTH = 512K
  RAM    (xrw) : ORIGIN = 0x20000000, LENGTH = 64K
  CCMRAM (xrw) : ORIGIN = 0x10000000, LENGTH = 16K
}

SECTIONS
{
  .isr_vector :
  {
    . = ALIGN(4);
    KEEP(*(.isr_vector))
    . = ALIGN(4);
  } >FLASH

  .text :
  {
    . = ALIGN(4);
    *(.text)
    *(.text*)
    *(.glue_7)
    *(.glue_7t)
    *(.eh_frame)
    KEEP(*(.init))
    KEEP(*(.fini))
    . = ALIGN(4);
    _etext = .;
  } >FLASH

  .rodata :
  {
    . = ALIGN(4);
    *(.rodata)
    *(.rodata*)
    . = ALIGN(4);
  } >FLASH

  .ARM.extab (READONLY) : { *(.ARM.extab* .gnu.linkonce.armextab.*) } >FLASH
  .ARM (READONLY) :
  {
    __exidx_start = .;
    *(.ARM.exidx*)
    __exidx_end = .;
  } >FLASH

  .preinit_array (READONLY) :
  {
    PROVIDE_HIDDEN(__preinit_array_start = .);
    KEEP(*(.preinit_array*))
    PROVIDE_HIDDEN(__preinit_array_end = .);
  } >FLASH
  .init_array (READONLY) :
  {
    PROVIDE_HIDDEN(__init_array_start = .);
    KEEP(*(SORT(.init_array.*)))
    KEEP(*(.init_array*))
    PROVIDE_HIDDEN(__init_array_end = .);
  } >FLASH
  .fini_array (READONLY) :
  {
    PROVIDE_HIDDEN(__fini_array_start = .);
    KEEP(*(SORT(.fini_array.*)))
    KEEP(*(.fini_array*))
    PROVIDE_HIDDEN(__fini_array_end = .);
  } >FLASH

  /* Initialised data: stored in flash, copied to RAM by the startup code. */
  _sidata = LOADADDR(.data);
  .data :
  {
    . = ALIGN(4);
    _sdata = .;
    *(.data)
    *(.data*)
    . = ALIGN(4);
    _edata = .;
  } >RAM AT> FLASH

  .bss :
  {
    . = ALIGN(4);
    _sbss = .;
    __bss_start__ = _sbss;
    *(.bss)
    *(.bss*)
    *(COMMON)
    . = ALIGN(4);
    _ebss = .;
    __bss_end__ = _ebss;
  } >RAM

  /* Not loaded: fails the link if heap plus stack do not fit after .bss. */
  ._user_heap_stack (NOLOAD) :
  {
    . = ALIGN(8);
    PROVIDE(end = .);
    PROVIDE(_end = .);
    . = . + _Min_Heap_Size;
    . = . + _Min_Stack_Size;
    . = ALIGN(8);
  } >RAM

  .ARM.attributes 0 : { *(.ARM.attributes) }
}
