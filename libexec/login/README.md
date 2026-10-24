# libexec/login

The authentication back ends login(1) calls.

Covers, from OpenBSD's base system at the pin (its path in OpenBSD's `src`):

- [`login_passwd`](login_passwd/) (libexec/login_passwd)
- [`login_chpass`](login_chpass/) (libexec/login_chpass)
- [`login_lchpass`](login_lchpass/) (libexec/login_lchpass)
- [`login_ldap`](login_ldap/) (libexec/login_ldap)
- [`login_radius`](login_radius/) (libexec/login_radius)
- [`login_reject`](login_reject/) (libexec/login_reject)
- [`login_skey`](login_skey/) (libexec/login_skey)
- [`login_token`](login_token/) (libexec/login_token)
- [`login_yubikey`](login_yubikey/) (libexec/login_yubikey)

Each entry is a program directory laid out as `docs/PROGRAM.md` says.
