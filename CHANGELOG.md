# Changelog

Format mengikuti [Keep a Changelog](https://keepachangelog.com/), versi mengikuti [SemVer](https://semver.org/).

## [0.1.1] - 2026-11-15

### Ditambahkan
- Aturan untuk nilai tanpa tanda kutip di file bergaya `.env` (`NAMA=nilai`, tanpa spasi), dengan filter yang sama seperti pendeteksi umum.
- Korpus evaluasi 55 kasus (delapan kasus aman bentuk `.env` ditambah). Precision 0,95 dan recall 1,00 pada sampel itu.
- Perbandingan berdampingan dengan gitleaks 8.26.0 (`eval/bandingkan_gitleaks.py`), dengan peringatan bias korpus di README.
- Kompatibel dengan kerangka `pre-commit` lewat `.pre-commit-hooks.yaml`, diuji dengan `pre-commit try-repo`.

## [0.1.0] - 2026-11-15

### Ditambahkan
- `scan`: memindai perubahan yang sudah di-`git add`, atau diff dari stdin (`--stdin`). Opsi `--quiet` dan `--ignore-file`.
- `install-hook` dan `uninstall-hook` untuk hook `pre-commit` yang gagal tertutup dan tidak menimpa hook lain tanpa `--force`.
- `scan-history`: seluruh riwayat (semua cabang dan tag), tiap rahasia dilaporkan sekali dengan commit pertama dan jumlah kemunculan.
- `.secretguardignore` berisi pola path, dengan penolakan pola terlalu luas dan negasi.
- Aturan untuk kunci berbentuk jelas dan pendeteksi umum berbasis keacakan dengan filter placeholder, path, URL, dan nama bergaya kode.
- Laporan `rich` yang aman: data dari luar dibungkus sebagai teks, karakter kendali diganti, `NO_COLOR` dihormati.
- Pratinjau rahasia disensor (paling banyak 4 karakter pertama).
- Korpus evaluasi 47 kasus dengan nilai rahasia yang dirakit saat dimuat; precision 0,95 dan recall 0,95.
- 186 test, `ruff` bersih, CI di GitHub Actions.

### Diketahui
- Salah alarm pada `session_token` berisi UUID, dan terlewat pada kata sandi `.env` tanpa tanda kutip.
- Belum dibandingkan dengan gitleaks, belum terintegrasi dengan kerangka `pre-commit`, kinerja repo besar belum diukur.
