"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { X } from "lucide-react";

type KeyboardInstance = {
  setInput: (input: string) => void;
  setOptions: (options: Record<string, unknown>) => void;
  destroy: () => void;
};

type KeyboardConstructor = new (
  rootElement: HTMLElement,
  options: Record<string, unknown>
) => KeyboardInstance;

type VirtualKeyboardProps = {
  value: string;
  isOpen: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onClose: () => void;
};

const INACTIVITY_TIMEOUT_MS = 15000;

const keyboardLayout = {
  default: [
    "1 2 3 4 5 6 7 8 9 0 {bksp}",
    "q w e r t y u i o p",
    "a s d f g h j k l ç",
    "{shift} z x c v b n m , . ?",
    "{space} {enter}",
  ],
  shift: [
    "! @ # $ % & * ( ) - {bksp}",
    "Q W E R T Y U I O P",
    "A S D F G H J K L Ç",
    "{shift} Z X C V B N M ; : /",
    "{space} {enter}",
  ],
};

const keyboardDisplay = {
  "{bksp}": "⌫",
  "{enter}": "Enviar",
  "{shift}": "⇧",
  "{space}": "Espaço",
};

export function VirtualKeyboard({
  value,
  isOpen,
  onChange,
  onSubmit,
  onClose,
}: VirtualKeyboardProps) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const keyboardRef = useRef<KeyboardInstance | null>(null);
  const inactivityTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onChangeRef = useRef(onChange);
  const onSubmitRef = useRef(onSubmit);
  const onCloseRef = useRef(onClose);
  const [layoutName, setLayoutName] = useState<"default" | "shift">("default");

  const clearInactivityTimer = useCallback(() => {
    if (inactivityTimerRef.current) {
      clearTimeout(inactivityTimerRef.current);
      inactivityTimerRef.current = null;
    }
  }, []);

  const resetInactivityTimer = useCallback(() => {
    clearInactivityTimer();

    if (!isOpen) return;

    inactivityTimerRef.current = setTimeout(() => {
      onCloseRef.current();
    }, INACTIVITY_TIMEOUT_MS);
  }, [clearInactivityTimer, isOpen]);

  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  useEffect(() => {
    onSubmitRef.current = onSubmit;
  }, [onSubmit]);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (isOpen) resetInactivityTimer();
    else clearInactivityTimer();

    return clearInactivityTimer;
  }, [clearInactivityTimer, isOpen, resetInactivityTimer]);

  useEffect(() => {
    let cancelled = false;

    async function mountKeyboard() {
      if (!isOpen || !rootRef.current || keyboardRef.current) return;

      const keyboardModule = (await import("simple-keyboard")) as {
        default: KeyboardConstructor;
      };

      if (cancelled || !rootRef.current) return;

      keyboardRef.current = new keyboardModule.default(rootRef.current, {
        layout: keyboardLayout,
        layoutName,
        display: keyboardDisplay,
        mergeDisplay: true,
        theme: "hg-theme-default totem-keyboard-theme",
        onChange: (input: string) => {
          resetInactivityTimer();
          onChangeRef.current(input);
        },
        onKeyPress: (button: string) => {
          resetInactivityTimer();

          if (button === "{shift}") {
            setLayoutName((current) => (current === "default" ? "shift" : "default"));
          }

          if (button === "{enter}") {
            onSubmitRef.current();
          }
        },
      });

      keyboardRef.current.setInput(value);
    }

    mountKeyboard();

    return () => {
      cancelled = true;
      if (!isOpen && keyboardRef.current) {
        keyboardRef.current.destroy();
        keyboardRef.current = null;
      }
    };
  }, [isOpen, layoutName, resetInactivityTimer, value]);

  useEffect(() => {
    keyboardRef.current?.setInput(value);
    if (isOpen) resetInactivityTimer();
  }, [isOpen, resetInactivityTimer, value]);

  useEffect(() => {
    keyboardRef.current?.setOptions({ layoutName });
  }, [layoutName]);

  useEffect(() => {
    if (!isOpen && keyboardRef.current) {
      keyboardRef.current.destroy();
      keyboardRef.current = null;
      setLayoutName("default");
      clearInactivityTimer();
    }
  }, [clearInactivityTimer, isOpen]);

  if (!isOpen) return null;

  return (
    <div className="virtual-keyboard-panel" onMouseDown={(event) => event.preventDefault()}>
      <div className="virtual-keyboard-header">
        <span>Teclado virtual</span>
        <button type="button" className="virtual-keyboard-close" onClick={onClose} aria-label="Fechar teclado">
          <X size={18} />
        </button>
      </div>
      <div ref={rootRef} className="virtual-keyboard" />
    </div>
  );
}
