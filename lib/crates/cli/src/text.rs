// Copyright (c) 2026 Emilio Navarrete Lineros <enavarre@outlook.com>
//
// Permission to use, copy, modify, and distribute this software for any
// purpose with or without fee is hereby granted, provided that the above
// copyright notice and this permission notice appear in all copies.
//
// THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
// WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
// MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
// ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
// WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
// ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
// OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

//! Text for a terminal: widths, the replacement of what must not reach it, sizes a human
//! reads, durations a human types.

/// The columns `s` takes on a terminal. Control characters count one, since they are
/// printed as `?`; everything else one per character. East Asian wide characters are not
/// yet counted double: that needs the locale tables of `data/locale`.
pub fn display_width(s: &str) -> usize {
    s.chars().count()
}

/// `s` with every control character and every DEL replaced by `?`, which is what `ls -q`
/// does and why a listing cannot inject escape sequences into the terminal.
pub fn sanitize(s: &str) -> String {
    s.chars()
        .map(|c| {
            if (c as u32) < 0x20 || c == '\u{7f}' {
                '?'
            } else {
                c
            }
        })
        .collect()
}

/// `bytes` as at most four characters with a power-of-two unit, the way `fmt_scaled(3)`
/// prints: `512`, `1.5K`, `12M`, `1.0G`. Below 1024 the number alone.
pub fn human_size(bytes: u64) -> String {
    const UNITS: [char; 6] = ['K', 'M', 'G', 'T', 'P', 'E'];
    if bytes < 1024 {
        return bytes.to_string();
    }
    let mut unit = 0;
    let mut scale: u64 = 1024;
    while unit + 1 < UNITS.len() && bytes >= scale * 1024 {
        scale *= 1024;
        unit += 1;
    }
    let whole = bytes / scale;
    let fract = bytes % scale;
    // one decimal, rounded, carried into the whole part when it rounds up to 10
    let mut tenths = (fract * 10 + scale / 2) / scale;
    let mut whole = whole;
    if tenths == 10 {
        whole += 1;
        tenths = 0;
    }
    if whole >= 1024 && unit + 1 < UNITS.len() {
        return format!("1.0{}", UNITS[unit + 1]);
    }
    if whole < 10 {
        format!("{whole}.{tenths}{}", UNITS[unit])
    } else {
        format!("{whole}{}", UNITS[unit])
    }
}

/// A duration a human types: `30s`, `15m`, `12h`, `7d`, `2w`, or plain seconds. Returns
/// seconds.
pub fn parse_duration(s: &str) -> Result<u64, String> {
    let s = s.trim();
    let (num, unit) = match s.char_indices().find(|(_, c)| !c.is_ascii_digit()) {
        Some((i, _)) => s.split_at(i),
        None => (s, "s"),
    };
    let n: u64 = num
        .parse()
        .map_err(|_| format!("`{s}` is not a duration like 7d, 12h, 30m, 45s"))?;
    let mult = match unit {
        "s" | "" => 1,
        "m" => 60,
        "h" => 3600,
        "d" => 86_400,
        "w" => 7 * 86_400,
        _ => return Err(format!("`{s}`: unit `{unit}` is not one of s, m, h, d, w")),
    };
    Ok(n * mult)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sizes_like_fmt_scaled() {
        let cases: [(u64, &str); 10] = [
            (0, "0"),
            (512, "512"),
            (1023, "1023"),
            (1024, "1.0K"),
            (1536, "1.5K"),
            (10 * 1024, "10K"),
            (1_048_576, "1.0M"),
            (1_500_000, "1.4M"),
            (1_073_741_824, "1.0G"),
            (1_099_511_627_776 - 1, "1.0T"),
        ];
        for (b, want) in cases {
            assert_eq!(human_size(b), want, "{b}");
        }
        assert!(human_size(u64::MAX).ends_with('E'));
    }

    #[test]
    fn durations() {
        assert_eq!(parse_duration("7d"), Ok(7 * 86_400));
        assert_eq!(parse_duration("90"), Ok(90));
        assert_eq!(parse_duration("2w"), Ok(14 * 86_400));
        assert!(parse_duration("3y").is_err());
        assert!(parse_duration("d").is_err());
    }

    #[test]
    fn sanitizing() {
        assert_eq!(sanitize("a\x1b[31mb\n"), "a?[31mb?");
        assert_eq!(display_width("héllo"), 5);
    }
}
