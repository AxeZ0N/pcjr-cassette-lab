#!/usr/bin/env python3
"""
PCjr stock IR keyboard emulator — integrated prototype.

Backend: reduced PCjrIRSender (frame/press/wave only, verified).
Outer layer: text input, atomic Shift handling, 50 chars/sec throttle.
Test harness: --run_test probe batteries (file / --spec / interactive).

Still stubs / intentionally omitted:
  - ANSI escape -> F-keys/arrows (ESC_MAP) : native PCjr codes unverified
  - Ctrl+Break                             : native sequence unverified
  - stateful make/break                    : out of scope by design
"""

import argparse
import time
import os
import pigpio

# ----------------------------------------------------------------------
# Verified scan tables
# ----------------------------------------------------------------------
SCAN = {
    "a": 0x1E,
    "b": 0x30,
    "c": 0x2E,
    "d": 0x20,
    "e": 0x12,
    "f": 0x21,
    "g": 0x22,
    "h": 0x23,
    "i": 0x17,
    "j": 0x24,
    "k": 0x25,
    "l": 0x26,
    "m": 0x32,
    "n": 0x31,
    "o": 0x18,
    "p": 0x19,
    "q": 0x10,
    "r": 0x13,
    "s": 0x1F,
    "t": 0x14,
    "u": 0x16,
    "v": 0x2F,
    "w": 0x11,
    "x": 0x2D,
    "y": 0x15,
    "z": 0x2C,
    "0": 0x0B,
    "1": 0x02,
    "2": 0x03,
    "3": 0x04,
    "4": 0x05,
    "5": 0x06,
    "6": 0x07,
    "7": 0x08,
    "8": 0x09,
    "9": 0x0A,
    " ": 0x39,
    "-": 0x0C,
    "=": 0x0D,
    "[": 0x1A,
    "]": 0x1B,
    ";": 0x27,
    "'": 0x28,
    "`": 0x29,
    "\\": 0x2B,
    ",": 0x33,
    ".": 0x34,
    "/": 0x35,
    "\n": 0x1C,
    "\r": 0x1C,
    "\t": 0x0F,
    "\b": 0x0E,
    "\x1b": 0x01,
    "\x7f": 0x0E,  # Backspace (DEL)
}

SHIFT = {
    "!": "1",
    "@": "2",
    "#": "3",
    "$": "4",
    "%": "5",
    "^": "6",
    "&": "7",
    "*": "8",
    "(": "9",
    ")": "0",
    "_": "-",
    "+": "=",
    "{": "[",
    "}": "]",
    ":": ";",
    '"': "'",
    "~": "`",
    "<": ",",
    ">": ".",
    "?": "/",
    "|": "\\",
}

# ----------------------------------------------------------------------
# Native PCjr F-key chords
# ----------------------------------------------------------------------
FKEY_SCANCODES = {
    1: 0x02,
    2: 0x03,
    3: 0x04,
    4: 0x05,
    5: 0x06,
    6: 0x07,
    7: 0x08,
    8: 0x09,
    9: 0x0A,
    10: 0x0B,
    11: 0x57,
    12: 0x58,
}

ESC_FKEY_MAP = {
    b"\x1bOP": 1,
    b"\x1bOQ": 2,
    b"\x1bOR": 3,
    b"\x1bOS": 4,
    b"\x1b[15~": 5,
    b"\x1b[17~": 6,
    b"\x1b[18~": 7,
    b"\x1b[19~": 8,
    b"\x1b[20~": 9,
    b"\x1b[21~": 10,
    b"\x1b[23~": 11,
    b"\x1b[24~": 12,
}

ESC_MAP = {
    b"\x1b[A": 0x48,
    b"\x1b[B": 0x50,
    b"\x1b[C": 0x4D,
    b"\x1b[D": 0x4B,
    b"\x1bOA": 0x48,
    b"\x1bOB": 0x50,
    b"\x1bOC": 0x4D,
    b"\x1bOD": 0x4B,
    b"\x1b[H": 0x47,
    b"\x1b[F": 0x4F,
    b"\x1b[5~": 0x49,
    b"\x1b[6~": 0x51,
    b"\x1b[2~": 0x52,
    b"\x1b[3~": 0x53,
    b"\x1bOP": 0x3B,
    b"\x1bOQ": 0x3C,
    b"\x1bOR": 0x3D,
    b"\x1bOS": 0x3E,
    b"\x1b[15~": 0x3F,
    b"\x1b[17~": 0x40,
    b"\x1b[18~": 0x41,
    b"\x1b[19~": 0x42,
    b"\x1b[20~": 0x43,
    b"\x1b[21~": 0x44,
    b"\x1b[23~": 0x57,
    b"\x1b[24~": 0x58,
}

SHIFT_SCAN = 0x2A
FN_SCAN = 0x54


# ----------------------------------------------------------------------
# Reduced sender — frame/press/wave only.
# ----------------------------------------------------------------------
class PCjrIRSender:
    def __init__(
        self,
        gpio=2,
        burst_us=62,
        start_silence_us=310,
        one_silence_us=377,
        zero_silence_1_us=220,
        zero_silence_2_us=157,
        frame_gap_us=1500,
        carrier_half_a=12,
        carrier_half_b=13,
    ):
        self.gpio = gpio
        self.pin = 1 << gpio
        self.burst_us = burst_us
        self.start_silence_us = start_silence_us
        self.one_silence_us = one_silence_us
        self.zero_silence_1_us = zero_silence_1_us
        self.zero_silence_2_us = zero_silence_2_us
        self.frame_gap_us = frame_gap_us
        self.carrier_half_a = carrier_half_a
        self.carrier_half_b = carrier_half_b
        self.pi = None

    def connect(self):
        self.pi = pigpio.pi()
        if not self.pi.connected:
            raise RuntimeError("pigpiod not running; run: sudo pigpiod")
        self.pi.set_mode(self.gpio, pigpio.OUTPUT)
        self.pi.write(self.gpio, 0)  # active-high idle = LED off
        return self

    def close(self):
        if self.pi is not None:
            self.pi.write(self.gpio, 0)
            self.pi.stop()
            self.pi = None

    # -- pulse primitives ------------------------------------------------
    def _idle_pulse(self, us):
        return pigpio.pulse(0, self.pin, us)

    def _led_on_pulse(self, us):
        return pigpio.pulse(self.pin, 0, us)

    def _silence(self, us):
        return [self._idle_pulse(us)]

    def _burst_for(self, us):
        """40 kHz carrier for `us` microseconds. Starts with the idle-low half."""
        pulses = []
        on = False
        remaining = us
        half = self.carrier_half_a
        while remaining > 0:
            d = min(half, remaining)
            pulses.append(self._led_on_pulse(d) if on else self._idle_pulse(d))
            remaining -= d
            on = not on
            half = (
                self.carrier_half_b
                if half == self.carrier_half_a
                else self.carrier_half_a
            )
        return pulses

    def _burst(self):
        return self._burst_for(self.burst_us)

    # -- frame construction ----------------------------------------------
    def build_frame(self, scan):
        """start + 8 data bits + odd parity + trailing frame gap."""
        p = []
        p += self._burst()
        p += self._silence(self.start_silence_us)

        ones = 0
        for bit in range(8):
            if (scan >> bit) & 1:
                p += self._burst()
                p += self._silence(self.one_silence_us)
                ones += 1
            else:
                p += self._silence(self.zero_silence_1_us)
                p += self._burst()
                p += self._silence(self.zero_silence_2_us)

        parity_bit = 0 if (ones & 1) else 1
        if parity_bit == 0:
            p += self._silence(self.zero_silence_1_us)
            p += self._burst()
            p += self._silence(self.zero_silence_2_us)
        else:
            p += self._burst()
            p += self._silence(self.one_silence_us)

        p += self._silence(self.frame_gap_us)
        return p

    def build_probe_wave(self, lead_us, pairs):
        """Custom stimulus: lead silence, then (burst_us, off_us) segments.

        No start/parity/stop structure. `pairs` is an ordered list of
        (on_us, off_us) tuples; the final off_us is the trailing silence.
        """
        p = []
        if lead_us > 0:
            p += self._silence(lead_us)
        for on_us, off_us in pairs:
            if on_us > 0:
                p += self._burst_for(on_us)
            if off_us > 0:
                p += self._silence(off_us)
        return p

    def key_press_pulses(self, scan):
        """make frame + break frame."""
        return self.build_frame(scan) + self.build_frame(scan | 0x80)

    # -- transport --------------------------------------------------------
    def send_wave(self, pulses):
        if not pulses:
            raise RuntimeError("empty wave pulse list")
        self.pi.wave_clear()
        added = self.pi.wave_add_generic(pulses)
        if added <= 0:
            raise RuntimeError(f"wave_add_generic failed: {added}")
        wid = self.pi.wave_create()
        if wid < 0:
            raise RuntimeError(f"wave_create failed: {wid}")
        self.pi.wave_send_once(wid)
        while self.pi.wave_tx_busy():
            time.sleep(0.005)
        self.pi.wave_delete(wid)

    def send_key_press(self, scan):
        self.send_wave(self.key_press_pulses(scan))


# ----------------------------------------------------------------------
# Emulator outer layer
# ----------------------------------------------------------------------
class PCjrEmulator(PCjrIRSender):
    """Outer character layer. Inherits transport and frame building."""

    def __init__(self, chars_per_sec=60):
        super().__init__()
        self.char_interval_s = 1.0 / max(1, chars_per_sec)
        self._last_char_time = 0.0

    def send_char(self, ch):
        """Send one character as an atomic make+break sequence.

        Throttling lives here, not in callers: every text path
        (--text, --stdin, send_text) is paced at chars_per_sec.
        """
        if ch in SCAN:
            self.send_key_press(SCAN[ch])
            #if ch == '\n': time.sleep(0.25)
            self._throttle()
            return

        if ch.isupper() and ch.lower() in SCAN:
            base = SCAN[ch.lower()]
        elif ch in SHIFT and SHIFT[ch] in SCAN:
            base = SCAN[SHIFT[ch]]
        else:
            raise ValueError(f"No scan code mapping for character: {ch!r}")

        self.send_wave(
            self.build_frame(SHIFT_SCAN)
            + self.key_press_pulses(base)
            + self.build_frame(SHIFT_SCAN | 0x80)
        )
        self._throttle()

    def send_text(self, text):
        for ch in text:
            self.send_char(ch)

    def _throttle(self):
        now = time.monotonic()
        wait = self._last_char_time + self.char_interval_s - now
        if wait > 0:
            time.sleep(wait)
        self._last_char_time = time.monotonic()

    def send_ansi_escape(self, seq):
        if isinstance(seq, str):
            seq = seq.encode("latin-1")

        if seq in ESC_FKEY_MAP:
            self.send_fkey(ESC_FKEY_MAP[seq])
            return

        try:
            scan = ESC_MAP[seq]
        except KeyError:
            raise KeyError(f"Unknown ANSI escape sequence: {seq!r}") from None
        self.send_key_press(scan)

    def send_scan(self, scan):
        self.send_key_press(scan)

    def _modifier_tap(self, mod_scan, tap_scan):
        self.send_wave(
            self.build_frame(mod_scan)
            + self.key_press_pulses(tap_scan)
            + self.build_frame(mod_scan | 0x80)
        )

    def send_ctrl_break(self):
        self._modifier_tap(FN_SCAN, SCAN["b"])

    def send_reset(self):
        combo = [0x1D, 0x38, 0x53]
        waves = []
        for x in combo: waves.extend(self.build_frame(x))
        for x in combo: waves.extend(self.build_frame(x|0x80))

        self.send_wave(waves) 

    def send_fkey(self, n):
        if n not in FKEY_SCANCODES:
            raise ValueError(f"Unsupported function key: F{n}")

        scan = FKEY_SCANCODES[n]
        if n <= 10:
            self._modifier_tap(FN_SCAN, scan)
        else:
            self.send_key_press(scan)

    def testing_macro(self, code: int, delay_after_enter: int, delay_between_codes: int):
        """
        Press enter, wait then send a single frame. Wait, then send it again.
        code: int = scancode / hex / int to encode just make sure it's a byte
        delay_after_enter: int = seconds
        delay_between_codes: int = micro seconds
        """
        original_frame_gap_us = self.frame_gap_us
        self.frame_gap_us = delay_between_codes

        test_frames = self.build_frame(code) + self.build_frame(code)
        self.frame_gap_us = original_frame_gap_us

        self.send_char('\n')
        time.sleep(delay_after_enter)
        self.send_wave(test_frames)


# ----------------------------------------------------------------------
# Probe battery — drop-in testing harness.
# ----------------------------------------------------------------------
def parse_trial_spec(text):
    """Parse 'label, lead_us, on,off, on,off, ...' into (label, lead, pairs)."""
    fields = [x.strip() for x in text.strip().split(",")]
    if len(fields) < 4 or len(fields) % 2 != 0:
        raise ValueError(f"bad trial spec (label,lead,on,off[,on,off...]): {text!r}")
    label = fields[0]
    lead_us = int(fields[1])
    pairs = [(int(fields[i]), int(fields[i + 1])) for i in range(2, len(fields), 2)]
    return label, lead_us, pairs


def load_trials(path):
    """Read trial specs from a file. '#' starts a comment; blank lines skipped."""
    trials = []
    with open(path) as fh:
        for line in fh:
            spec = line.split("#", 1)[0].strip()
            if spec:
                trials.append(parse_trial_spec(spec))
    return trials


def interactive_trials():
    """Prompt for trial specs until a blank line."""
    print("[harness] trial format: label, lead_us, on,off, on,off, ...", flush=True)
    print("[harness] blank line finishes input.", flush=True)
    trials = []
    while True:
        spec = input("trial> ").strip()
        if not spec:
            break
        trials.append(parse_trial_spec(spec))
    return trials


class PCjrTestHarness(PCjrEmulator):
    """Prime once per battery, then one wave per BASIC INPUT release."""

    def __init__(self, post_run_wait_s=3.0, chars_per_sec=60):
        super().__init__(chars_per_sec=chars_per_sec)
        self.post_run_wait_s = post_run_wait_s

    def _send_line(self, text):
        for ch in text:
            self.send_char(ch)

    def run_battery(self, trials, arm_delay_s=0.4, cls_wait_s=1.0, run_wait_s=4):
        print("[harness] send: cls", flush=True)
        self._send_line("cls\n")
        time.sleep(cls_wait_s)

        for label, lead_us, pairs in trials:
            print(
                f"[harness] {label}: run -> enter -> arm {arm_delay_s}s -> "
                f"lead={lead_us}us pairs={pairs}",
                flush=True,
            )
            self._send_line("run\n")
            time.sleep(run_wait_s)
            self._send_line("\n")  # release BASIC INPUT
            time.sleep(arm_delay_s)
            self.send_wave(self.build_probe_wave(lead_us, pairs))
            time.sleep(self.post_run_wait_s)
            print(f"[harness] {label}: done", flush=True)

    def run_suite(self, trials, battery_size=4, arm_delay_s=0.4, load_delay=6):
        n_batches = (len(trials) + battery_size - 1) // battery_size
        for b, i in enumerate(range(0, len(trials), battery_size), 1):
            batch = trials[i:i + battery_size]
            print(
                f"[harness] battery {b}/{n_batches} "
                f"(slots={battery_size}, trials={len(batch)}): "
                f"{[t[0] for t in batch]}",
                flush=True,
            )
            self.run_battery(batch, arm_delay_s=arm_delay_s, run_wait_s=load_delay)
            if b < n_batches:
                input(f"[harness] transcribed battery {b}? press Enter for next battery... ")
            else:
                print("[harness] suite complete", flush=True)


# ----------------------------------------------------------------------
# stdin passthrough
# ----------------------------------------------------------------------
import select
import sys
import termios
import tty


def _read_escape_sequence(fd):
    seq = b"\x1b"
    while True:
        ready, _, _ = select.select([fd], [], [], 0.5)
        if not ready:
            break
        try:
            b = os.read(fd, 1)
        except OSError:
            break
        if not b:
            break
        seq += b
        if seq in ESC_MAP:
            return seq
        if not any(k.startswith(seq) for k in ESC_MAP):
            break

    return seq


def stdin_passthrough(emu):
    fd = sys.stdin.fileno()

    if not sys.stdin.isatty():
        data = sys.stdin.buffer.read()
        emu.send_text(data.decode("ascii", errors="replace"))
        return

    print("Begin typing", flush=True)

    old_attrs = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)

        while True:
            ready, _, _ = select.select([fd], [], [], None)
            if not ready:
                continue
            b = os.read(fd, 1)
            if not b:
                break

            if b == b"\x03":
                break
            if b == b"\x02":
                emu.send_ctrl_break()
                continue

            if b == b"\x1b":
                seq = _read_escape_sequence(fd)
                try:
                    emu.send_ansi_escape(seq)
                except KeyError:
                    if seq == b"\x1b":
                        emu.send_char("\x1b")
                continue

            ch = b.decode("ascii", errors="replace")
            if ch:
                emu.send_char(ch)

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
        emu.close()


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="PCjr stock IR keyboard emulator")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--char", help="send exactly one character")
    group.add_argument("--text", help="send a text payload")
    group.add_argument("--scan", help="send one raw scancode as hex, e.g. 48")
    group.add_argument(
        "--escape", help="send one ANSI escape sequence as hex, e.g. 1b5b41"
    )
    group.add_argument("--cc", action="store_true", help="Send Ctrl+C to PCJr")
    group.add_argument("--reset", action="store_true", help="Send Ctrl+Alt+Del to PCJr")
    group.add_argument(
        "--stdin", action="store_true", help="stream stdin to the PCjr interactively"
    )
    group.add_argument("--fkey", type=int, help="send F1-F12 (1-12)")
    group.add_argument(
        "--run_test",
        nargs="?",
        const="__interactive__",
        metavar="FILE",
        help="probe battery: FILE, interactive if bare, --spec for one trial",
    )

    # Harness tunables (not part of the exclusive group).
    parser.add_argument(
        "--spec",
        help="single trial spec: label,lead,on,off[,on,off...]",
    )
    parser.add_argument(
        "--arm", type=float, default=0.4, help="arming delay after Enter (s)"
    )
    parser.add_argument(
        "--post", type=float, default=3.0, help="post-run wait for BASIC dump (s)"
    )
    parser.add_argument(
        "--battery", type=int, default=4, help="trials per RUN (must match BASIC)"
    )
    parser.add_argument( "--cps", type=int, default=60, help="characters per second throttle"
    )

    args = parser.parse_args()

    if args.run_test is not None:
        harness = PCjrTestHarness(post_run_wait_s=args.post, chars_per_sec=args.cps)

        harness.connect()
        try:
            if args.run_test == "__interactive__":
                trials = (
                    [parse_trial_spec(args.spec)]
                    if args.spec
                    else interactive_trials()
                )
            else:
                trials = load_trials(args.run_test)

            if not trials:
                raise SystemExit("no trials loaded")

            harness.run_suite(
                trials,
                battery_size=args.battery,
                arm_delay_s=args.arm,
            )
        finally:
            harness.close()
        return

    emu = PCjrEmulator(chars_per_sec=args.cps)
    emu.connect()
    try:
        if args.stdin:
            stdin_passthrough(emu)
            return
        if args.char is not None:
            if len(args.char) != 1:
                raise SystemExit("--char expects exactly one character")
            emu.send_char(args.char)
        elif args.scan is not None:
            emu.send_key_press(int(args.scan, 16))
        elif args.escape is not None:
            emu.send_ansi_escape(bytes.fromhex(args.escape))
        elif args.cc:
            emu.send_ctrl_break()
        elif args.reset:
            emu.send_reset()
        elif args.fkey is not None:
            emu.send_fkey(args.fkey)
        else:
            emu.send_text(args.text)
    finally:
        emu.close()


if __name__ == "__main__":
    main()
