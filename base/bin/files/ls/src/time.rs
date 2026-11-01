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

//! The three ways a time is written: ISO 8601 for a terminal, POSIX's two shapes for a pipe
//! (`Oct 24 13:05` for the last six months, `Oct 24  2025` beyond or in the future), and
//! RFC 3339 with nanoseconds for the record. The zone comes from `sys::local_time`; the
//! formatting is pure over a [`LocalTime`], so it is tested without touching `TZ`.

use sys::LocalTime;

const MONTHS: [&str; 12] = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

/// Half a year of seconds, as `ls(1)` counts it: 365 days over two.
const SIX_MONTHS: i64 = 365 * 24 * 60 * 60 / 2;

const EPOCH: LocalTime = LocalTime {
    year: 1970,
    month: 1,
    day: 1,
    hour: 0,
    minute: 0,
    second: 0,
    utc_offset: 0,
};

fn local(secs: i64) -> LocalTime {
    // A time the C library cannot break down is shown as the epoch, as ls does.
    sys::local_time(secs)
        .or_else(|| sys::local_time(0))
        .unwrap_or(EPOCH)
}

/// `2026-10-24 13:05`.
pub fn iso(secs: i64) -> String {
    iso_of(local(secs))
}

fn iso_of(t: LocalTime) -> String {
    format!(
        "{:04}-{:02}-{:02} {:02}:{:02}",
        t.year, t.month, t.day, t.hour, t.minute
    )
}

/// POSIX's long-listing date: recent files with the time of day, the rest with the year.
pub fn posix(secs: i64, now: i64) -> String {
    posix_of(local(secs), secs, now)
}

fn posix_of(t: LocalTime, secs: i64, now: i64) -> String {
    let month = MONTHS[(t.month as usize).clamp(1, 12) - 1];
    if secs <= now - SIX_MONTHS || secs > now {
        format!("{month} {:>2}  {:04}", t.day, t.year)
    } else {
        format!("{month} {:>2} {:02}:{:02}", t.day, t.hour, t.minute)
    }
}

/// `2026-10-24T13:05:09.123456789-03:00`, the record's form.
pub fn rfc3339(secs: i64, nanos: u32) -> String {
    rfc3339_of(local(secs), nanos)
}

fn rfc3339_of(t: LocalTime, nanos: u32) -> String {
    let sign = if t.utc_offset < 0 { '-' } else { '+' };
    let off = t.utc_offset.abs();
    format!(
        "{:04}-{:02}-{:02}T{:02}:{:02}:{:02}.{:09}{sign}{:02}:{:02}",
        t.year,
        t.month,
        t.day,
        t.hour,
        t.minute,
        t.second,
        nanos,
        off / 3600,
        (off % 3600) / 60
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    const T: LocalTime = LocalTime {
        year: 2026,
        month: 4,
        day: 24,
        hour: 2,
        minute: 26,
        second: 40,
        utc_offset: -3 * 3600,
    };

    #[test]
    fn iso_and_rfc3339() {
        assert_eq!(iso_of(T), "2026-04-24 02:26");
        assert_eq!(rfc3339_of(T, 5), "2026-04-24T02:26:40.000000005-03:00");
        assert_eq!(
            rfc3339_of(
                LocalTime {
                    utc_offset: 5 * 3600 + 1800,
                    ..T
                },
                0
            ),
            "2026-04-24T02:26:40.000000000+05:30"
        );
    }

    #[test]
    fn posix_six_month_rule() {
        let now = 1_777_000_000;
        assert_eq!(posix_of(T, now - 60, now), "Apr 24 02:26");
        assert_eq!(posix_of(T, now - SIX_MONTHS, now), "Apr 24  2026"); // exactly six months: the year
        assert_eq!(posix_of(T, now - SIX_MONTHS + 1, now), "Apr 24 02:26");
        assert_eq!(posix_of(T, now + 1, now), "Apr 24  2026"); // the future: the year
        assert_eq!(posix_of(EPOCH, 0, now), "Jan  1  1970");
    }

    #[test]
    fn the_real_clock_round_trips_the_epoch_year() {
        // Whatever TZ is, the epoch falls on the last day of 1969 or the first of 1970.
        let s = iso(0);
        assert!(
            s.starts_with("1969-12-31") || s.starts_with("1970-01-01"),
            "{s}"
        );
    }
}
