#!/usr/bin/env python3
# Copyright (c) 2026 Emilio Navarrete Lineros <enavarre@outlook.com>
#
# Permission to use, copy, modify, and distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
"""An internal check that a release's artifact installs: from the two releases alone, a
throwaway install medium, an install on a fresh disk in QEMU answered from the console, and
that disk booted alone to a shell.

usage: install-check.py <tag> [<arch>]      (arch: arm64, the default)

Reads only local files, downloads nothing: Userland's artifact dist/userland-<tag>-<arch>.tar.zst
(checked against its .sha256; `just dist` made it, or the main session downloaded the published
one there) and the Kernel's release KERNEL.toml pins, in upstream/kernel/<release>/ (`just
fetch-build`). It needs the host tools of `just world <arch> tree host` (makefs, sha256) and
QEMU with its EDK2 firmware (EMIBSD_QEMU_SHARE, /opt/homebrew/opt/qemu/share/qemu).

The medium is OS's to make and ship; this one is never published or kept: it is laid out as
the proof of 2026-11-06 (bsd.rd = the Kernel's bsd.RAMDISK with miniroot80.fs set in, the
sets, INSTALL.<arch>, bsd.mp and bsd.rd under 8.0/<arch> with their SHA256, /etc/boot.conf
naming bsd.rd, an El Torito EFI image with BOOTAA64.EFI), made under
target/install-check/<tag>-<arch>/ and removed with the disks at the end, pass or fail. The
console transcripts stay beside it: <tag>-<arch>.install.log and .boot.log.

QEMU runs under the machine's lock, /tmp/emibsd/ci.lock, a directory made with mkdir and
shared with the Kernel's and OS's sessions (never flock): the check waits for it, up to
EMIBSD_LOCK_WAIT seconds (two hours by default), and never breaks another's.

Exit 0 when the install completes without the questions that mean a defect (a missing
INSTALL.<arch>, a set failing its checksum) and the installed disk reaches a shell; 1 otherwise,
with the reason; 2 for a usage error.
"""
import hashlib
import os
import shutil
import struct
import subprocess
import sys
import tarfile
import threading
import time
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOST = ROOT / "target/host/bin"
WORK = ROOT / "target/install-check"
LOCK = Path("/tmp/emibsd/ci.lock")
QEMU_SHARE = Path(os.environ.get("EMIBSD_QEMU_SHARE", "/opt/homebrew/opt/qemu/share/qemu"))
OSREV, VERSION = "80", "8.0"
SETS = ("base", "comp", "man", "game")

# The installer's questions, in the order it asks them, and the answers: a fresh disk, the
# automatic layout, the sets from the medium.
INSTALL_ANSWERS = [
    ("(I)nstall, (U)pgrade, (A)utoinstall or (S)hell?", "i\n"),
    ("Terminal type?", "\n"),
    ("System hostname?", "emibsd\n"),
    ("Network interface to configure?", "done\n"),
    ("DNS domain name?", "\n"),
    ("DNS nameservers?", "\n"),
    ("Password for root account?", "emibsd\n"),
    ("(again)", "emibsd\n"),
    ("Start sshd(8) by default?", "no\n"),
    ("Setup a user?", "no\n"),
    ("Which disk is the root disk?", "sd0\n"),
    ("Encrypt the root disk", "\n"),
    ("Use (W)hole disk", "\n"),
    ("Use (A)uto layout", "a\n"),
    ("Location of sets?", "cd0\n"),
    ("Pathname to the sets?", "\n"),
    ("Set name(s)?", "done\n"),
    ("Continue without verification?", "yes\n"),   # the sets are not signed yet
    ("Location of sets?", "done\n"),
    ("What timezone are you in?", "UTC\n"),
    ("Exit to (S)hell, (H)alt or (R)eboot?", "h\n"),
]
INSTALL_REJECTS = ["panic:", "Failed to install bootblocks", "Installation of ", "Checksum test for",
                   "found here anyway", "not a valid choice"]
BOOT_PROBE = "uname -a; ls -l /bsd /usr/mdec/BOOTAA64.EFI; zstd -V; df -h /; echo up-$((6*7))\n"


def kernel_release(arch: str) -> Path:
    pin = tomllib.loads((ROOT / "KERNEL.toml").read_text())["kernel"]
    tarball = ROOT / "upstream/kernel" / pin["release"] / f"kernel-{pin['release']}-{arch}.tar.zst"
    if not tarball.exists():
        raise SystemExit(f"install-check: no {tarball.relative_to(ROOT)} (just fetch-build, from the main session)")
    if hashlib.sha256(tarball.read_bytes()).hexdigest() != pin["sha256"][arch]:
        raise SystemExit(f"install-check: {tarball.name} does not match KERNEL.toml's sum")
    return tarball


def artifact(tag: str, arch: str) -> Path:
    tarball = ROOT / "dist" / f"userland-{tag}-{arch}.tar.zst"
    sums = tarball.with_name(tarball.name + ".sha256")
    if not tarball.exists() or not sums.exists():
        raise SystemExit(f"install-check: no {tarball.relative_to(ROOT)} and its .sha256 (just dist {arch})")
    subprocess.run(["shasum", "-a", "256", "-c", sums.name], cwd=tarball.parent, check=True,
                   stdout=subprocess.DEVNULL)
    return tarball


def unpack(tarball: Path, dest: Path) -> Path:
    """The one directory a release's artifact holds, checked against its own SHA256."""
    dest.mkdir(parents=True)
    zstd = subprocess.Popen(["zstd", "-dcq", str(tarball)], stdout=subprocess.PIPE)
    with tarfile.open(fileobj=zstd.stdout, mode="r|") as tar:
        tar.extractall(dest, filter="data")
    if zstd.wait():
        raise SystemExit(f"install-check: zstd failed on {tarball.name}")
    top = dest / tarball.name.removesuffix(".tar.zst")
    lines = [l for l in (top / "SHA256").read_text().splitlines() if l]
    check = "".join(f"{l.split(' = ')[1]}  {l.split('(')[1].split(')')[0]}\n" for l in lines)
    subprocess.run(["shasum", "-a", "256", "-c", "-"], cwd=top, input=check, text=True, check=True,
                   stdout=subprocess.DEVNULL)
    return top


def rdsetroot(kernel: Path, image: Path) -> None:
    """The image into an ELF64 kernel's rd_root_image, at most rd_root_size bytes."""
    data, img = bytearray(kernel.read_bytes()), image.read_bytes()
    if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
        raise SystemExit(f"install-check: {kernel.name} is not a little-endian ELF64")
    shoff, = struct.unpack_from("<Q", data, 0x28)
    shentsize, shnum = struct.unpack_from("<HH", data, 0x3a)
    secs = [struct.unpack_from("<IIQQQQIIQQ", data, shoff + i * shentsize) for i in range(shnum)]
    symtab = next(s for s in secs if s[1] == 2)
    strtab = secs[symtab[6]]
    where = {}
    for off in range(symtab[4], symtab[4] + symtab[5], 24):
        name, _, _, shndx, value, _ = struct.unpack_from("<IBBHQQ", data, off)
        n = data[strtab[4] + name:data.index(b"\0", strtab[4] + name)].decode()
        if n in ("rd_root_image", "rd_root_size"):
            sec = secs[shndx]
            where[n] = sec[4] + (value - sec[3])
    size, = struct.unpack_from("<I", data, where["rd_root_size"])
    if len(img) > size:
        raise SystemExit(f"install-check: {image.name} is {len(img)} bytes, rd_root_size {size}")
    data[where["rd_root_image"]:where["rd_root_image"] + len(img)] = img
    kernel.write_bytes(data)


def medium(work: Path, userland: Path, kernel: Path, arch: str) -> Path:
    cd, efi = work / "cd", work / "efi"
    sets_dir = cd / VERSION / arch
    for d in (sets_dir, cd / "etc", efi / "EFI/BOOT"):
        d.mkdir(parents=True)
    rd = sets_dir / "bsd.rd"
    shutil.copy(kernel / "bsd.RAMDISK", rd)
    rdsetroot(rd, userland / f"miniroot{OSREV}.fs")
    files = [f"{s}{OSREV}.tar.zst" for s in SETS] + [f"INSTALL.{arch}"]
    for f in files:
        shutil.copy(userland / f, sets_dir / f)
    shutil.copy(kernel / "bsd.mp", sets_dir / "bsd.mp")
    sums = subprocess.run([str(HOST / "sha256"), *files, "bsd.mp", "bsd.rd"], cwd=sets_dir,
                          capture_output=True, text=True, check=True).stdout
    (sets_dir / "SHA256").write_text(sums)
    (cd / "etc/boot.conf").write_text(f"set image /{VERSION}/{arch}/bsd.rd\n")
    shutil.copy(kernel / "BOOTAA64.EFI", efi / "EFI/BOOT/BOOTAA64.EFI")
    makefs = str(HOST / "makefs")
    subprocess.run([makefs, "-t", "msdos", "-s", "2880k", str(sets_dir / "cdbr"), str(efi)],
                   check=True, stdout=subprocess.DEVNULL)
    iso = work / f"install{OSREV}.iso"
    subprocess.run([makefs, "-t", "cd9660", "-o",
                    f"label=EMIBSD_{OSREV},rockridge,bootimage=efi;{sets_dir / 'cdbr'},no-emul-boot",
                    str(iso), str(cd)], check=True, stdout=subprocess.DEVNULL)
    return iso


class MachineLock:
    """/tmp/emibsd/ci.lock, the machine's QEMU lock: a directory, its owner line inside."""

    def __init__(self, what: str):
        self.what = what

    def __enter__(self):
        wait = float(os.environ.get("EMIBSD_LOCK_WAIT", "7200"))
        LOCK.parent.mkdir(parents=True, exist_ok=True)
        start, told = time.time(), False
        while True:
            try:
                LOCK.mkdir()
                break
            except FileExistsError:
                if not told:
                    owner = (LOCK / "owner").read_text().strip() if (LOCK / "owner").exists() else "unknown"
                    print(f"install-check: waiting for the QEMU lock, held by: {owner}", flush=True)
                    told = True
                if time.time() - start > wait:
                    raise SystemExit(f"install-check: the QEMU lock was not free in {wait:.0f}s; not broken")
                time.sleep(15)
        (LOCK / "owner").write_text(f"Userland install-check: {self.what}, {time.ctime()}\n")
        return self

    def __exit__(self, *_):
        (LOCK / "owner").unlink(missing_ok=True)
        LOCK.rmdir()


def console(log: Path, answers, expects, rejects, *, cd: Path | None = None, disk: Path,
            timeout: float, stall: float, settle: float = 0) -> str | None:
    """QEMU virt with EDK2 from its serial console: answers each question once it shows
    after the previous answer, until every expected line has been seen. None on success,
    else the reason."""
    vars_fd = log.with_suffix(".vars.fd")
    shutil.copy(QEMU_SHARE / "edk2-arm-vars.fd", vars_fd)
    cmd = ["qemu-system-aarch64", "-M", "virt,acpi=off", "-cpu", "cortex-a72", "-m", "1024M", "-smp", "2",
           "-display", "none", "-monitor", "none", "-no-reboot", "-serial", "stdio",
           "-drive", f"if=pflash,format=raw,readonly=on,file={QEMU_SHARE / 'edk2-aarch64-code.fd'}",
           "-drive", f"if=pflash,format=raw,file={vars_fd}",
           "-netdev", "user,id=n0", "-device", "virtio-net-device,netdev=n0",
           "-drive", f"if=none,format=raw,file={disk},id=hd0", "-device", "virtio-blk-device,drive=hd0"]
    if cd:
        cmd += ["-device", "virtio-scsi-device,id=scsi0",
                "-drive", f"if=none,format=raw,media=cdrom,file={cd},id=cd0", "-device", "scsi-cd,drive=cd0,bootindex=0"]
    vm = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    buf, guard = bytearray(), threading.Lock()

    def reader():
        while chunk := vm.stdout.read1(4096):
            with guard:
                buf.extend(chunk)

    threading.Thread(target=reader, daemon=True).start()
    start = changed = time.time()
    nxt, frm, seen, reason = 0, 0, 0, None
    try:
        while True:
            time.sleep(0.2)
            with guard:
                text = buf.decode("utf-8", "replace")
            if nxt < len(answers) and (i := text.find(answers[nxt][0], frm)) >= 0:
                time.sleep(0.3)
                for ch in answers[nxt][1]:
                    vm.stdin.write(ch.encode())
                    vm.stdin.flush()
                    time.sleep(0.02)
                print(f"  {time.time() - start:4.0f}s  {answers[nxt][0]!r} <- {answers[nxt][1]!r}", flush=True)
                frm, nxt = len(text), nxt + 1
            if bad := next((r for r in rejects if r in text), None):
                reason = f"the console showed {bad!r}"
                break
            if nxt == len(answers) and all(e in text for e in expects):
                print(f"  {time.time() - start:4.0f}s  every expected line seen", flush=True)
                end = time.time() + settle   # halt's sync reaches the disk before QEMU goes
                while time.time() < end and vm.poll() is None:
                    time.sleep(0.5)
                break
            if vm.poll() is not None:
                reason = f"QEMU ended ({vm.returncode}) with answer {nxt} of {len(answers)} pending"
                break
            if len(text) != seen:
                seen, changed = len(text), time.time()
            elif time.time() - changed > stall:
                reason = f"no output for {stall:.0f}s at answer {nxt} of {len(answers)}"
                break
            if time.time() - start > timeout:
                reason = f"timed out after {timeout:.0f}s at answer {nxt} of {len(answers)}"
                break
    finally:
        vm.kill()
        vm.wait()
        log.write_bytes(bytes(buf))
        vars_fd.unlink(missing_ok=True)
    return reason


def remove(tree: Path) -> None:
    """A tree removed whole, read-only directories (a release's, as unpacked) included."""
    if not tree.exists():
        return
    for d in (tree, *(p for p in tree.rglob("*") if p.is_dir() and not p.is_symlink())):
        d.chmod(0o755)
    shutil.rmtree(tree)


def main() -> int:
    args = sys.argv[1:]
    if not 1 <= len(args) <= 2 or (len(args) == 2 and args[1] != "arm64"):
        print(__doc__, file=sys.stderr)
        return 2
    tag, arch = args[0], (args[1:] or ["arm64"])[0]
    for tool in ("makefs", "sha256"):
        if not (HOST / tool).exists():
            raise SystemExit(f"install-check: no target/host/bin/{tool} (just host-make; just world {arch} tree host)")
    userland_tarball, kernel_tarball = artifact(tag, arch), kernel_release(arch)
    work = WORK / f"{tag}-{arch}"
    remove(work)
    logs = {n: WORK / f"{tag}-{arch}.{n}.log" for n in ("install", "boot")}
    try:
        userland = unpack(userland_tarball, work / "userland")
        kernel = unpack(kernel_tarball, work / "kernel")
        iso = medium(work, userland, kernel, arch)
        disk = work / "disk.img"
        with open(disk, "wb") as fh:
            fh.truncate(3 << 30)
        with MachineLock(f"installing {tag} {arch}"):
            print(f"install-check: installing {tag} {arch} from a throwaway medium", flush=True)
            reason = console(logs["install"], INSTALL_ANSWERS, ["CONGRATULATIONS!", "halted by root"],
                             INSTALL_REJECTS, cd=iso, disk=disk, timeout=2400, stall=120, settle=60)
            if reason:
                print(f"install-check: FAIL: the install: {reason}; see {logs['install'].relative_to(ROOT)}")
                return 1
            print("install-check: booting the installed disk alone", flush=True)
            reason = console(logs["boot"], [("login:", "root\n"), ("Password:", "emibsd\n"), ("# ", BOOT_PROBE)],
                             ["up-42"], ["panic:"], disk=disk, timeout=1200, stall=300)
            if reason:
                print(f"install-check: FAIL: the installed disk: {reason}; see {logs['boot'].relative_to(ROOT)}")
                return 1
        lines = logs["boot"].read_text(errors="replace").replace("\r", "").splitlines()
        first = next(i for i, l in enumerate(lines) if l.startswith("EmiBSD ") and "GENERIC#" in l)
        last = next(i for i, l in enumerate(lines) if l.startswith("up-42"))
        print("install-check: PASS", *(f"  {l}" for l in lines[first:last]), sep="\n")
        return 0
    finally:
        remove(work)   # the medium and the disk are never kept


if __name__ == "__main__":
    sys.exit(main())
