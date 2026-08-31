Work Scheduler is a local-first desktop application for planning, validating,
finalizing, and printing employee work schedules in small pharmacies. It runs
entirely on your own computer: no account, no server, and no internet connection.
All operational data stays in a private local SQLite database.

## Downloads

| Platform | File | Notes |
| --- | --- | --- |
| macOS (Apple Silicon) | `work-scheduler-macos-arm64.dmg` | M1 or newer; macOS 13 or newer |
| macOS (Intel) | `work-scheduler-macos-x86_64.dmg` | macOS 13 or newer |
| Windows | `work-scheduler-windows-x86_64.zip` | Windows 10 or newer |
| Linux | `work-scheduler-linux-x86_64.tar.gz` | glibc 2.35 or newer |

### Installing on macOS

1. Open the `.dmg` and drag **Work Scheduler** into `Applications`.
2. The build is not signed with an Apple Developer certificate, so the first
   launch has to be approved: right-click the application, choose **Open**, and
   confirm the dialog. Later launches work normally.

### Installing on Windows

1. Unpack the `.zip` anywhere you like, for example `C:\Program Files\Work Scheduler`.
2. Run `Work Scheduler.exe`. The build is unsigned, so SmartScreen may warn once:
   choose **More info**, then **Run anyway**.

### Installing on Linux

1. Unpack the archive: `tar -xzf work-scheduler-linux-x86_64.tar.gz`.
2. Run `"Work Scheduler/Work Scheduler"`.

## What this release contains

- **Employee management** for pharmacists and pharmacy technicians, keeping
  inactive people visible in historical schedules.
- **Day-by-person schedule grid** with direct keyboard entry, flexible time
  formats (`8-16`, `8:30-17:00`, `8.30 do 16.30`), and automatic hour totals.
- **Opening hours and Polish public holidays**, including movable Easter-based
  dates, with manual exceptions for individual days. Each schedule keeps its own
  copy of the opening hours, so later settings changes never rewrite past work.
- **Validation before finalization**: open days with nobody assigned, periods
  without pharmacist coverage, shifts outside opening hours, and employees with
  no assigned work.
- **Printing and PDF export** for the whole pharmacy and for individual
  employees, with corrected table framing on printed pages.
- **Polish and English interface**, with the printout language chosen
  independently of the interface language.
- **Light, dark, and system appearance**, following the operating system theme.

## Privacy and data

Schedules, employees, and settings are written to a private per-user database
directory with restrictive file permissions. Exports and backups are written only
where you ask for them. Nothing is transmitted anywhere.

## Requirements

Nothing needs to be installed beforehand. Python and Qt are bundled inside each
download.

## License

Work Scheduler is free software under the GNU Affero General Public License
v3.0 only. The complete source code is in this repository. Copyright and
licensing information for bundled dependencies and assets is provided in
`THIRD_PARTY_NOTICES.md`, which is included in every application package.
