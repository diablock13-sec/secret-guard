# secret-guard

![CI](https://github.com/diablock13-sec/secret-guard/actions/workflows/ci.yml/badge.svg)

Mencegah API key, token, dan password ikut ter-commit. Memindai perubahan yang
sudah di-`git add`, memasang hook `pre-commit` yang memblokir commit berisi rahasia,
dan bisa memindai seluruh riwayat Git. Proyek belajar. Baca bagian **Keterbatasan**
sebelum dipakai untuk sesuatu yang penting.

## Pasang

    git clone https://github.com/diablock13-sec/secret-guard.git
    cd secret-guard
    uv sync
    uv run secret-guard --version

Butuh [uv](https://docs.astral.sh/uv/) dan Python sesuai file `.python-version`.

## Pakai

Pindai perubahan yang sudah di-`git add` di repo tempat kamu berada:

    uv run secret-guard scan

Pindai diff dari tempat lain lewat stdin:

    git diff --cached | uv run secret-guard scan --stdin

Pindai seluruh riwayat (semua cabang dan tag), misalnya 500 commit terbaru:

    uv run secret-guard scan-history --max-commits 500

Kode keluar: `0` bersih, `1` ada temuan, `2` kesalahan. Opsi lain: `--quiet`
(tidak mencetak apa pun kalau bersih) dan `--ignore-file FILE` (ganti
`.secretguardignore`).

## Hook pre-commit

`install-hook` memasang hook `pre-commit` yang menjalankan pemindaian sebelum
commit tersimpan, dan `uninstall-hook` menghapusnya. Opsi lengkap:

    uv run secret-guard install-hook --help

Perilaku yang disengaja:

- Gagal tertutup: kalau interpreter hilang, commit tetap diblokir.
- Hook milik orang lain tidak pernah ditimpa tanpa `--force`; hook lama dipindah ke `.bak`.
- Opsi `git diff` dipaku (`--src-prefix`, `--no-renames`, `--no-textconv`) supaya
  konfigurasi Git pengguna tidak merusak pembacaan diff.
- Hook hanya berlaku di mesin lokal. `git commit --no-verify` melewatinya, dan
  tidak ada pemeriksaan di sisi server.

### Lewat kerangka pre-commit

Kalau proyekmu sudah memakai [pre-commit](https://pre-commit.com/), tambahkan ke
`.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/diablock13-sec/secret-guard
    rev: v0.1.3
    hooks:
      - id: secret-guard
```

Hook ini menjalankan `secret-guard scan` pada perubahan yang sudah di-`git add`
dan tidak memakai daftar nama file dari pre-commit. Diuji dengan
`pre-commit try-repo`: commit bersih lolos, commit berisi nilai mirip rahasia
ditolak dengan kode keluar 1. Hook hanya berlaku di mesin yang memasangnya dan
tetap bisa dilewati dengan `--no-verify`.

## Yang dideteksi

Aturan berbentuk jelas: `aws-access-key-id`, `github-token`, `slack-token`, `telegram-bot-token`, `private-key`, `stripe-secret-key`, `google-api-key`, `jwt`, `url-credentials`.
Ditambah pendeteksi umum untuk nilai acak yang ditugaskan ke nama seperti
`api_key`, `secret`, `token`, atau `password`. Nilai harus cukup panjang dan
acak, bukan placeholder, bukan path, bukan URL, dan bukan nama bergaya kode.
Hanya baris yang **ditambah** pada diff yang diperiksa.

Rahasia tidak pernah dicetak utuh: pratinjau paling banyak 4 karakter pertama.

## Mengabaikan temuan

Berkas `.secretguardignore` berisi pola path, satu per baris. Aturannya:

- Baris yang diawali `#` adalah komentar.
- Negasi `!` ditolak.
- Pola yang terlalu luas, seperti `*`, ditolak.
- Temuan yang diabaikan tetap dilaporkan di stderr, tidak diam-diam.
- Satu baris bisa dikecualikan dengan komentar `secret-guard:ignore` di baris itu.

## Evaluasi

Korpus 55 kasus di `eval/corpus.jsonl`. Nilai rahasia di berkas itu **dirakit dari
potongan** saat dimuat, dan sebuah test memastikan nilai utuhnya tidak pernah
tertulis di berkas, jadi repo ini tidak memuat teks yang mirip kunci sungguhan.
Hasil terbaru ada di `eval/hasil-v0.1.1.txt`. Hasil v0.1.0 (47 kasus) tetap
tersimpan di `eval/hasil-final.txt`.

| kelompok | kasus | TP | FP | FN | TN |
|----------|-------|----|----|----|----|
| didukung | 13 | 13 | 0 | 0 | 0 |
| heuristik | 6 | 6 | 0 | 0 | 0 |
| aman | 19 | 0 | 0 | 0 | 19 |
| aman-sulit | 17 | 0 | 1 | 0 | 16 |
| **semua** | **55** | **19** | **1** | **0** | **35** |

Precision 0,95 dan recall 1,00. Perjalanannya: awal precision 0,71 dan recall 0,59,
putaran kedua 0,80 dan 0,94, putaran ketiga 0,95 dan 0,95, lalu v0.1.1 (aturan
untuk nilai tanpa tanda kutip di file bergaya `.env`) 0,95 dan 1,00.

Baca angka ini dengan hati-hati. Korpus ditulis oleh penulis yang juga menyetel
aturannya, jadi angkanya optimistis. Recall 1,00 khususnya hanya berlaku pada
sampel: aturan `.env` ditulis setelah kasusnya terlihat gagal, dan delapan kasus
aman baru ditambahkan sesudah aturan itu ada. Delapan kasus itu hanya membuktikan
aturan baru tidak merusak kasus yang terpikirkan, bukan bentuk `.env` lain.
Korpus kecil dan belum berisi repo sungguhan.

Kegagalan yang diketahui:

- Salah alarm: `session_token = "<UUID>"` dianggap rahasia oleh pendeteksi umum.
- Aturan nilai tanpa kutip sengaja sempit. Tidak tercakup: nilai YAML tanpa kutip
  (`password: nilai`), nilai dengan spasi di sekitar `=`, nama kunci yang tidak di
  awal baris, dan nilai yang diawali `$`.

## Keterbatasan

- Berbasis pola dan heuristik. Rahasia berbentuk tak biasa bisa lolos, dan nilai
  acak yang bukan rahasia bisa terdeteksi.
- `scan` hanya melihat baris yang ditambah. Rahasia yang sudah ada di riwayat
  ditemukan oleh `scan-history`. **Rahasia yang pernah ter-push harus dicabut
  dan diganti**, menghapusnya dari berkas tidak cukup.
- Hook bisa dilewati dengan `--no-verify` dan hanya berlaku lokal.
- Baris lebih panjang dari 10.000 karakter hanya dipindai 10.000 karakter
  pertamanya. Rahasia setelah batas itu (misalnya di berkas hasil bundler satu
  baris) tidak terdeteksi.
- Kinerja pada satu mesin dan repo buatan (302 commit, 19 MB teks, satu baris
  2 MB, biner 20 MB), jadi anggap sebagai gambaran kasar: `scan-history` sekitar
  5 detik dan 129 MB memori, `scan` pada 19 MB teks yang di-stage sekitar 5 detik
  dan 82 MB, pada biner 20 MB sekitar 0,2 detik. Memori kira-kira tiga kali
  ukuran diff karena diff dibaca utuh. Repo sungguhan belum diukur.
- Perbandingan berdampingan baru dengan gitleaks, pada korpus yang ditulis untuk
  secret-guard (lihat bagian di bawah). TruffleHog belum dibandingkan.

## Dibandingkan dengan alat lain

- **gitleaks**: pemindai rahasia yang matang dengan aturan jauh lebih banyak,
  konfigurasi, dan dukungan luas. Pakai untuk repo sungguhan.
- **TruffleHog**: banyak detektor dan mampu memverifikasi apakah sebuah kunci
  masih aktif. Pakai kalau perlu itu.
- **secret-guard**: kecil dan mudah dibaca, dengan hook yang gagal tertutup, laporan
  yang tidak membocorkan rahasia, dan evaluasi yang jujur dengan angka. Cocok
  untuk belajar atau repo pribadi berisiko rendah, bukan menggantikan alat di atas.

### Perbandingan berdampingan dengan gitleaks

Korpus 55 kasus yang sama dijalankan lewat gitleaks 8.26.0 (paket Kali, aturan
bawaan, tanpa konfigurasi). Tiap kasus ditulis ke satu berkas berisi satu baris,
lalu dinilai dengan aturan yang sama seperti secret-guard. Ulangi dengan
`uv run python eval/bandingkan_gitleaks.py`. Hasil ada di `eval/hasil-gitleaks.txt`.

| alat | TP | FP | FN | TN | precision | recall |
|------|----|----|----|----|-----------|--------|
| secret-guard | 19 | 1 | 0 | 35 | 0,95 | 1,00 |
| gitleaks 8.26.0 | 15 | 4 | 4 | 32 | 0,79 | 0,79 |

**Jangan baca ini sebagai bukti secret-guard lebih baik.** Korpus ditulis oleh
penulis secret-guard, dan kelompok `didukung` dibuat dari aturannya sendiri, jadi
hasilnya condong ke alat ini. Korpusnya kecil, dan satu baris per berkas tidak
sama dengan memindai repo sungguhan. Dua catatan tambahan:

- Pada perbandingan 47 kasus sebelumnya, gitleaks tercatat 0,83 dan 0,79. Turunnya
  precision ke 0,79 **bukan perubahan gitleaks**: alat dan versinya sama, hanya
  korpusnya yang bertambah.
- Salah alarm baru gitleaks, `dotenv-checksum-name`, berasal dari kasus yang
  ditulis untuk menguji filter nama-hash milik secret-guard. Kasus itu tidak adil
  dihitung sebagai kekurangan gitleaks.

Perbedaan per kasus:

- **Hanya secret-guard yang menangkap:** `github-pat`, `telegram-bot`,
  `private-key-header`, dan `db-url-password`. Alasan gitleaks melewatkannya belum
  diselidiki. Dugaan: kasus satu baris merugikan aturan yang butuh konteks
  (misalnya blok kunci privat). Itu dugaan, belum diuji.
- **Salah alarm di keduanya:** `uuid-session-token`.
- **Salah alarm hanya di gitleaks:** `sha-named-token`, `stripe-test-key`, dan
  `dotenv-checksum-name` (lihat catatan di atas). Label "aman" untuk kunci uji
  Stripe adalah penilaian penulis korpus.
- **Hanya gitleaks yang menangkap:** tidak ada lagi pada korpus ini. Sebelum
  v0.1.1, `dotenv-unquoted-password` hanya tertangkap gitleaks. Celah itu ditutup
  dengan aturan baru, dan penutupannya disetel setelah kasusnya terlihat.

Untuk repo sungguhan, gitleaks tetap pilihan yang lebih tepat. TruffleHog belum
dibandingkan.

## Pengembangan

    uv run pytest
    uv run ruff check .

Test memakai repo Git sungguhan dengan konfigurasi global diisolasi, dan semua
rahasia palsu dirakit saat runtime.

## Lisensi

MIT. Lihat `LICENSE`.
