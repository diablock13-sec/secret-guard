# Changelog

Format mengikuti [Keep a Changelog](https://keepachangelog.com/), versi mengikuti [SemVer](https://semver.org/).

## [0.1.5] - 2026-11-17

### Diubah
- `scan` kini membaca `git diff --cached` dan stdin baris demi baris, bukan sekaligus. Memori puncak proses Python pada 19 MB teks yang di-stage turun dari 82 MB menjadi 24-25 MB (repo uji buatan, satu mesin, tiga jalan). Waktu tetap sekitar 5 detik: 4,9-5,0 detik sebelum dan 5,2-5,8 detik sesudah, selisih kecil yang mungkin biaya pemrosesan per baris.
- `scan-history` tidak berubah secara terukur: 5,5-5,8 detik dan 38 MB proses Python, sebelum dan sesudah (repo uji 302 commit).
- Pembaca keluaran git dipakai bersama oleh `scan` dan `scan-history` (internal).

### Ditambahkan
- `tests/test_streaming_scan.py`: dua test membuktikan aliran baris dan teks utuh menghasilkan baris tambahan yang sama, termasuk akhir baris CRLF. Tiga test menjaga perilaku `scan` pada repo Git sungguhan, termasuk gagal tertutup (kode keluar 2) di luar repo.

### Diketahui
- File besar tetap dipindai penuh, tidak dilewati.
- Pengukuran memakai satu mesin dan repo buatan. Angka memori adalah proses Python saja, tidak termasuk proses `git`.

## [0.1.4] - 2026-11-16

### Diubah
- Batas pemindaian per baris naik dari 10.000 menjadi 1.000.000 karakter. Rahasia di antara karakter ke-10.000 dan ke-1.000.000 sebuah baris kini terdeteksi (di v0.1.3 lolos tanpa tanda). Satu baris 1 MB butuh sekitar 1,1 detik.
- `scan-history` pada repo uji (302 commit, 19 MB teks, satu baris 2 MB) naik dari 5,3 detik menjadi 7,1 detik karena baris 2 MB kini dipindai sebagian. Memori puncak tetap 129 MB.

### Ditambahkan
- Peringatan di stderr untuk baris yang melebihi batas: nama file, nomor baris, panjang, dan jumlah karakter yang dipindai. Peringatan TIDAK memblokir commit dan tidak mengubah kode keluar, karena file hasil generate (bundle, lockfile) akan mendorong orang memakai `--no-verify`. `scan-history` melaporkan satu peringatan per file, dan file yang cocok dengan `.secretguardignore` tidak diperingatkan. Maksimal 5 peringatan dicetak, sisanya diringkas.
- 4 test untuk peringatan (`tests/test_long_line_warning.py`) dan 5 test untuk batas baru (`tests/test_long_lines.py`).

### Diketahui
- Baris lebih panjang dari 1.000.000 karakter tetap hanya dipindai bagian awalnya. Rahasia di luar batas itu tidak terdeteksi, hanya diperingatkan.
- Kerangka `pre-commit` menyembunyikan keluaran hook yang lolos. Peringatan baris panjang baru terlihat dengan `pre-commit run -v`.

## [0.1.3] - 2026-11-15

### Diperbaiki
- Pencarian awalan nama kunci (`key_name`) berwaktu kuadratik pada deretan panjang sebelum kata kunci. Satu baris 10.000 karakter butuh sekitar 0,7 detik di v0.1.2 dan 13 detik pada 40.000 karakter. Kini dibatasi 64 karakter ke belakang, dan waktunya linear (40.000 karakter sekitar 0,014 detik). Catatan v0.1.2 menyebut waktunya sudah linear, dan itu keliru untuk pola ini.

### Ditambahkan
- Uji yang menjaga pencarian awalan nama kunci tetap linear, dan uji yang menjaga filter nama-hash tetap bekerja.

### Diketahui
- Baris lebih panjang dari 10.000 karakter hanya dipindai 10.000 karakter pertamanya. Rahasia di luar batas itu tidak terdeteksi. Pengukuran menunjukkan pemindaian tanpa batas itu linear sampai 2 MB, jadi celah ini bisa ditutup di rilis berikutnya.

## [0.1.2] - 2026-11-15

### Diperbaiki
- Dua pola umum (`GENERIC` dan `GENERIC_UNQUOTED`) berwaktu kuadratik pada baris panjang yang memuat kata kunci berulang. Contoh: 20.000 karakter `token` butuh sekitar 2,4 detik di v0.1.0 dan v0.1.1, dan 40.000 karakter sekitar 15 detik. Awalan dan akhiran nama kunci kini dibatasi 64 karakter, dan waktunya linear (40.000 karakter di bawah 0,05 detik).

### Ditambahkan
- Uji kinerja regex (`tests/test_regex_perf.py`).

### Diketahui
- Baris lebih panjang dari 10.000 karakter hanya dipindai 10.000 karakter pertamanya. Rahasia di luar batas itu tidak terdeteksi (terbukti pada uji dengan baris 12.000 karakter).

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
