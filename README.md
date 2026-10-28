# Catatan APRILcell

Aplikasi keuangan pribadi lokal — Python + Flask + SQLite. Berjalan sepenuhnya di komputer pengguna, dibuka lewat browser di `http://127.0.0.1:5000`. Tidak ada database cloud, tidak ada PHP/MySQL/Node. Fungsi inti dapat digunakan tanpa internet setelah instalasi (Bootstrap 5 dan Chart.js tersimpan lokal di `app/static/vendor/`).

## Struktur

Proyek ini memakai struktur modular di dalam paket `app/`:

- `app.py` — entry point (`python app.py`, debug OFF, host 127.0.0.1:5000)
- `config.py`, `extensions.py`
- `app/__init__.py` — application factory, seed data awal
- `app/models.py` — semua model SQLAlchemy (nominal selalu integer rupiah, tidak pernah float)
- `app/utils.py` — helper rupiah, ledger transaksi, pembalikan/koreksi, audit
- Blueprint: `app/auth/`, `app/dashboard/`, `app/accounts/`, `app/transactions/`, `app/transfers/`, `app/debts/`, `app/expenses/`, `app/uncollected_income/`, `app/reports/`, `app/backup/`, `app/settings/`
- Template nyata ada di `app/templates/` dan aset di `app/static/` (pilihan ini menggantikan folder `templates/` + `static/` di root yang disebut di brief — folder root tersebut tetap disediakan sebagai penanda struktur, tetapi Flask memakai yang di dalam `app/`). Ini satu-satunya lokasi template/static agar tidak ada duplikasi yang membingungkan.
- `instance/` — database permanen `catatan_aprilcell.db` + `secret_key.txt` (tidak masuk Git)
- `backups/` — file backup SQLite (tidak masuk Git)
- `migrations/` — Flask-Migrate / Alembic
- `tests/` — pytest

## Instalasi di Windows

Syarat: Python 3.11+ terinstal (centang **Add python.exe to PATH** saat install Python).

1. Download / clone / pull repo ini ke PC.
2. Klik dua kali **`install.bat`** — memeriksa Python, membuat `.venv`, memasang `requirements.txt`, menyiapkan folder data dan database **tanpa menghapus database yang sudah ada**.
3. Klik dua kali **`run.bat`** — menjalankan aplikasi dari virtual environment dan membuka browser otomatis ke `http://127.0.0.1:5000`.
4. Pada kunjungan pertama Anda diarahkan ke **Setup Administrator**: buat username dan password Anda sendiri (minimal password 6 karakter). Tidak ada password bawaan. Setelah akun dibuat, halaman setup terkunci permanen.
5. Hentikan server dengan `Ctrl+C` di jendela console, atau tutup jendela tersebut.

Manual (opsional):

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app.py
```

## Penggunaan

- **Dashboard** — total saldo aktual, saldo per rekening, pemasukan/pengeluaran periode berjalan, piutang, utang pribadi, dan uang belum diterima (empat kategori ditampilkan terpisah dan tidak dicampur), grafik, ringkasan harian/mingguan/bulanan, transaksi terbaru, tombol cepat.
- **Saldo Semua Rekening** — 11 rekening awal tersimpan dengan saldo Rp 0: BCA, BRI, BNI, Mandiri, SeaBank, AlloBank, GoPay, DANA Rudi, DANA Tamara, Uang, Cash. Isi saldo awal lewat tombol *Saldo Awal* sesuai kenyataan. Rekening yang punya riwayat tidak dihapus permanen — cukup dinonaktifkan.
- **Transaksi Saldo** — Tambah Saldo, Kurangi Saldo (ditolak bila saldo tidak mencukupi; saldo tidak boleh negatif), Penyesuaian Saldo (saldo target + alasan wajib, tercatat di audit).
- **Transfer Antar-Rekening** — atomik, kedua sisi terhubung lewat satu ID transfer, total saldo gabungan tidak berubah, dan tidak dihitung sebagai pemasukan/pengeluaran di laporan.
- **Buku Utang dan Piutang** — tambah orang, catat pinjaman (saldo rekening sumber berkurang, piutang bertambah — bukan pengeluaran), pembayaran sebagian / pelunasan (saldo bertambah — bukan pendapatan baru), dan utang pribadi (penerimaan menaikkan saldo + kewajiban; pembayaran menurunkan keduanya).
- **Pengeluaran Harian** — kategori awal 12 buah, dapat ditambah/diedit/dinonaktifkan di Pengaturan. Setiap pengeluaran mengurangi rekening sumber dan masuk laporan. Filter tanggal/kategori/rekening/orang/pencarian, total per hari/kategori/orang.
- **Uang Masuk Belum Diambil** — catat hak yang belum diterima (tidak masuk saldo aktual), terima sebagian berkali-kali ke rekening pilihan sampai status menjadi *Sudah diambil*.
- **Laporan Keuangan** — Harian, Mingguan (Senin–Minggu), Bulanan, atau rentang khusus; zona waktu Asia/Jakarta. Menampilkan saldo awal/akhir periode, pemasukan eksternal, pengeluaran, transfer internal (terpisah), rincian, breakdown per kategori/orang/rekening, ekspor CSV, dan halaman cetak.
- **Riwayat Transaksi** — filter lengkap; pembatalan/koreksi selalu lewat transaksi pembalikan + audit log (tidak ada edit/hapus diam-diam).
- **Pengaturan** — ganti password, kelola kategori, lihat audit log dan info aplikasi.

## Backup dan Restore

Menu **Backup dan Restore**:

- *Buat Backup Sekarang* membuat `backups/backup-YYYYMMDD-HHMMSS.db` memakai API backup SQLite yang aman terhadap transaksi aktif.
- File backup bisa di-download dari daftar.
- *Restore* memvalidasi file dulu (integrity check + tabel wajib), lalu otomatis membuat backup `pre-restore-*.db` dari database aktif sebelum mengganti, jadi restore selalu bisa dibatalkan.
- **Sangat disarankan menyalin file backup ke media lain** (flashdisk / cloud pribadi) secara berkala — backup di folder yang sama tidak melindungi dari kerusakan disk.

## Pemulihan Akun Lokal

Password disimpan sebagai hash Werkzeug dan **tidak bisa dibaca kembali** — tidak ada cara melihat password lama, dan prosedur ini tidak membocorkannya. Jika lupa password:

1. Tutup aplikasi.
2. Backup folder `instance/` terlebih dahulu.
3. Di komputer Anda sendiri, jalankan dari folder proyek:

```
.venv\Scripts\python -c "from app import create_app; from extensions import db; from app.models import User; a=create_app(); ctx=a.app_context(); ctx.push(); u=User.query.first(); u.set_password('PasswordBaruAnda'); db.session.commit(); print('Password diganti untuk', u.username)"
```

4. Login dengan password baru tersebut, lalu segera ganti lagi lewat menu Pengaturan.

## Upgrade Tanpa Kehilangan Data

1. Backup lewat menu Backup (atau salin `instance/catatan_aprilcell.db`).
2. Pull / salin source code baru **tanpa menimpa folder `instance/` dan `backups/`**.
3. Jalankan `install.bat` lagi (aman, tidak mereset database) lalu `run.bat`. Migrasi skema memakai Flask-Migrate (`flask db migrate` / `flask db upgrade`); aplikasi tidak pernah menjalankan DROP TABLE atau reset saat start.

## Troubleshooting

- **`Python tidak ditemukan`** — install Python 3.11+ dan centang *Add python.exe to PATH*, lalu ulangi `install.bat`.
- **Port 5000 sudah dipakai** — tutup aplikasi lain yang memakai port 5000, atau tutup jendela Catatan APRILcell yang masih berjalan.
- **Halaman setup tidak muncul / langsung login** — normal bila administrator sudah pernah dibuat; setup memang terkunci.
- **Saldo terasa tidak cocok** — cek Riwayat Transaksi: saldo adalah jumlah semua `signed_amount` transaksi aktif per rekening; koreksi selalu lewat pembalikan, jadi jejaknya selalu terlihat.
- **Setelah restore data terlihat lama** — restore mengganti database dengan isi file backup terpilih; gunakan file `pre-restore-*.db` untuk kembali ke kondisi sebelum restore.

## Pengujian

```
.venv\Scripts\python -m pytest tests/ -v
```

Test memakai database SQLite file temporer terpisah dan mencakup: instalasi pertama, setup admin + penguncian setup, login benar/salah, proteksi halaman, saldo awal + invariant saldo = jumlah ledger, tambah/kurangi saldo, penolakan saldo kurang, transfer (terhubung + total tetap), pinjaman 200.000 → bayar 50.000 → sisa 150.000 → lunas, utang pribadi, pengeluaran, uang belum diambil 500.000 → terima 200.000 → sisa 300.000 → terima penuh, laporan harian/mingguan/bulanan + CSV + cetak, koreksi/pembalikan + audit, backup + restore, persistensi antar-restart, validasi input berbahaya (negatif, nol, transfer rekening sama, string XSS ter-escape), dan penanda responsif (viewport, navigasi bawah, breakpoint CSS).

Hasil pengujian nyata dicatat saat proyek diserahkan — lihat laporan penyerahan / jalankan sendiri perintah di atas. Jangan menganggap fitur teruji bila test-nya belum benar-benar dijalankan.
