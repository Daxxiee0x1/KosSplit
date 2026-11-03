# Product Requirements Document

## KosSplit, Android Split Bill dan Expense Tracker

| Atribut | Nilai |
|---|---|
| Versi dokumen | 2.1 |
| Status | Siap implementasi MVP |
| Platform | Android APK |
| Bahasa utama | Python 3.10+ |
| Framework UI | Kivy 2.3 |
| Integrasi native | Google ML Kit melalui Pyjnius |
| Penyimpanan | SQLite lokal |
| Target pengguna | Penghuni kos, kontrakan, dan kelompok mahasiswa |
| Model penggunaan | Local-first, satu perangkat |

## 1. Ringkasan produk

KosSplit membantu penghuni kos mencatat pengeluaran pribadi dan membagi biaya bersama tanpa spreadsheet atau pencarian ulang di grup chat. Produk berfokus pada ketepatan hitung, kejelasan utang, dan input yang cepat saat pengguna baru selesai makan, belanja, atau membayar kebutuhan kos.

Aplikasi berjalan sebagai APK Android dan tidak memerlukan browser, akun, server, atau koneksi internet untuk fungsi utama.

## 2. Masalah

Penghuni kos sering mengalami masalah berikut:

1. Catatan tagihan tenggelam di grup chat.
2. Pajak, biaya layanan, ongkir, dan diskon dibagi tanpa rumus yang konsisten.
3. Pembulatan membuat total porsi berbeda dari total struk.
4. Utang silang menghasilkan terlalu banyak transfer.
5. Pengeluaran patungan terpisah dari catatan pengeluaran pribadi.
6. Pencatatan manual membuat pengguna lupa memasukkan transaksi.
7. Rekap bulanan untuk evaluasi atau tugas kuliah sulit dibuat.

## 3. Tujuan

### 3.1 Tujuan produk

- Menyelesaikan pembuatan tagihan bersama dalam maksimal empat langkah.
- Menjaga jumlah seluruh porsi sama dengan total akhir sampai satu Rupiah.
- Menampilkan siapa membayar siapa tanpa pengguna menghitung ulang.
- Menggabungkan porsi tagihan dengan catatan pengeluaran pribadi.
- Menghasilkan laporan PDF dan Excel yang dapat diperiksa.
- Tetap berguna saat perangkat tidak terhubung ke internet.

### 3.2 Bukan tujuan MVP

- Sinkronisasi beberapa perangkat
- Login dan akun daring
- Pembayaran otomatis melalui bank
- Chat antaranggota
- Marketplace atau promosi
- Dukungan mata uang selain Rupiah

## 4. Pengguna

### 4.1 Penanggung bayar

Orang yang membayar lebih dahulu. Ia perlu mencatat struk, memilih metode pembagian, dan mendapatkan jumlah yang harus dibayar setiap anggota.

### 4.2 Anggota kos

Orang yang memiliki porsi tagihan. Ia perlu melihat nominal kewajiban dan tujuan pembayaran dengan jelas.

### 4.3 Pemilik catatan

Pemilik perangkat. Ia perlu melihat arus kas, budget, transaksi pribadi, dan seluruh utang aktif.

## 5. Prinsip produk

1. **Tepat sebelum cantik.** Perhitungan dan pembulatan tidak boleh menghasilkan selisih.
2. **Offline sebagai kondisi utama.** Tidak ada fungsi inti yang bergantung pada jaringan.
3. **Bahasa manusia.** Gunakan "dibayar Ayu" dan "Bima membayar Ayu", bukan istilah akuntansi yang tidak perlu.
4. **Satu fokus per layar.** Ringkasan untuk memahami kondisi, Tagihan untuk membagi biaya, Catatan untuk transaksi, Anggota untuk data orang.
5. **Data milik pengguna.** Tidak ada pengiriman data diam-diam.

## 6. Ruang lingkup fitur

### FR-01 Manajemen anggota, P0

Pengguna dapat:

- Menambahkan nama panggilan
- Menambahkan nomor WhatsApp
- Menambahkan bank atau e-wallet
- Menentukan budget bulanan
- Menandai satu anggota sebagai pemilik catatan
- Melihat daftar anggota

Kriteria penerimaan:

- Nama wajib diisi.
- Budget disimpan sebagai integer Rupiah.
- Data tetap tersedia setelah aplikasi ditutup.
- Minimal dua anggota diperlukan untuk membuat tagihan.

### FR-02 Pencatatan transaksi, P0

Pengguna dapat mencatat:

- Pemasukan
- Pengeluaran
- Pemilik transaksi
- Kategori
- Keterangan
- Nominal
- Tanggal transaksi

Kategori awal:

- Makan & Minum
- Kebutuhan Kos
- Transportasi
- Akademik
- Hiburan
- Lainnya
- Patungan

Kriteria penerimaan:

- Nominal harus lebih dari nol.
- Porsi tagihan anggota selain penanggung bayar otomatis menjadi transaksi kategori Patungan.
- Ringkasan bulan menggunakan tanggal transaksi, bukan waktu input.

### FR-03 Pembuatan tagihan, P0

Data tagihan:

- Judul
- Tanggal
- Penanggung bayar
- Metode pembagian
- Subtotal
- Pajak, layanan, dan ongkir
- Diskon
- Total akhir
- Porsi setiap anggota

Rumus total:

```text
total_akhir = subtotal + pajak_layanan_ongkir - diskon
```

Semua nominal disimpan sebagai integer.

### FR-04 Bagi rata, P0

Total akhir dibagi kepada anggota yang dipilih. Jika total tidak habis dibagi, sisa Rupiah didistribusikan secara deterministik.

Kriteria penerimaan:

- Setiap anggota berbeda maksimal satu Rupiah.
- Jumlah porsi selalu sama dengan total akhir.

### FR-05 Nominal kustom, P0

Pengguna memasukkan nominal untuk setiap anggota.

Kriteria penerimaan:

- Tidak ada nominal negatif.
- Jumlah nominal harus sama dengan total akhir.
- Tagihan tidak dapat disimpan jika jumlah berbeda.

### FR-06 Persentase, P0

Pengguna memasukkan persentase setiap anggota.

Kriteria penerimaan:

- Total persentase tepat 100.
- Hasil dikonversi menjadi integer Rupiah.
- Sisa pembulatan didistribusikan berdasarkan pecahan terbesar.

### FR-07 Per item, P0

Setiap item memiliki nama, harga, dan satu atau beberapa anggota. Item yang dimiliki beberapa anggota dibagi rata terlebih dahulu.

Biaya tambahan dan diskon dibagi proporsional berdasarkan subtotal setiap anggota:

```text
porsi_i = subtotal_i + subtotal_i / total_subtotal
          × (pajak_layanan_ongkir - diskon)
```

Kriteria penerimaan:

- Setiap item memiliki minimal satu anggota.
- Jumlah harga item sama dengan subtotal.
- Jumlah porsi sama dengan total akhir.
- Item dapat dimiliki lebih dari satu anggota.

### FR-08 Penyederhanaan utang, P1

Sistem menghitung saldo bersih:

```text
saldo_bersih = total_piutang - total_utang
```

Greedy matching mempertemukan debitur dan kreditur sampai seluruh saldo nol.

Kriteria penerimaan:

- Total debit sama dengan total kredit.
- Rantai Ayu ke Bima dan Bima ke Caca dapat disederhanakan menjadi Ayu ke Caca jika nominal sama.
- Tidak ada transfer bernilai nol.

### FR-09 Dashboard, P0

Dashboard menampilkan:

- Pemasukan bulan ini
- Pengeluaran bulan ini
- Selisih arus kas
- Transfer utang yang disarankan
- Pengeluaran berdasarkan kategori
- Aksi cepat membuat transaksi dan tagihan

Kriteria penerimaan:

- Dashboard diperbarui setelah data disimpan.
- Kondisi tanpa data memiliki pesan yang membantu.
- Nilai uang menggunakan pemisah ribuan Indonesia.

### FR-10 Budget, P1

Pemilik catatan dapat menentukan budget bulanan.

Perilaku:

- Di bawah 80 persen: status aman
- 80 sampai 99 persen: peringatan
- 100 persen atau lebih: budget terlampaui

Pengembangan lanjutan perlu menampilkan progress dan sisa nominal pada Dashboard.

### FR-11 Ekspor laporan, P1

Pengguna dapat menghasilkan:

- Excel berisi sheet Tagihan dan Transaksi
- PDF berisi ringkasan bulan dan tagihan terbaru

Kriteria penerimaan:

- Nominal Excel tetap berupa angka.
- File memiliki tanggal pada nama.
- Kegagalan penulisan file menghasilkan pesan yang jelas.

### FR-12 Pengingat WhatsApp, P1

Dari slip utang, sistem membuka WhatsApp dengan pesan:

```text
Halo Bima, ini pengingat dari KosSplit.
Kamu perlu membayar Rp42.500 ke Ayu.
Transfer ke BCA mobile: 1234567890
Terima kasih.
```

Kriteria penerimaan:

- Nomor 08xx dikonversi ke format 628xx.
- Tombol hanya muncul jika nomor WhatsApp debitur tersedia.

### FR-13 Pindai struk, P1

Arsitektur:

1. Google ML Kit Document Scanner membuka kamera, mendeteksi tepi, dan meluruskan struk. Galeri dapat dipakai sebagai alternatif.
2. Google ML Kit Text Recognition membaca teks di perangkat.
3. Python memanggil kedua library Java tersebut melalui Pyjnius.
4. Python menyusun ulang baris dari koordinat kotak teks agar nama item dan harga yang terpisah kolom kembali satu baris.
5. Parser Python mengenali item, kuantitas, subtotal, pajak, layanan, ongkir, diskon, dan total.
6. Pengguna memeriksa dan mengedit hasil.
7. Hasil diteruskan ke tagihan per item.

Kriteria penerimaan:

- Tidak ada gambar yang dikirim ke server.
- Tidak memerlukan izin kamera atau penyimpanan.
- OCR tidak langsung menyimpan tagihan.
- Setiap angka dapat diperbaiki.
- Format angka 25.000, 25,000, 25.000,00, dan Rp 25.000 dikenali.
- Baris tunai, kembalian, kartu, QRIS, tanggal, dan jam diabaikan.
- Total tagihan yang disimpan sama persis dengan total struk.
- Tersedia alternatif tempel teks dan OCR desktop dengan Tesseract.

### FR-14 Pembayaran melalui aplikasi bank, P1

KosSplit tidak login ke akun bank. Sistem menyiapkan transfer dan menyerahkan konfirmasi ke aplikasi resmi.

Perilaku:

1. Anggota menyimpan bank atau e-wallet beserta nomor rekening.
2. Slip utang di Ringkas dapat diketuk.
3. Sistem menampilkan nominal, penerima, bank, dan nomor rekening.
4. Tombol utama menyalin nomor rekening dan membuka aplikasi bank atau e-wallet penerima.
5. Jika aplikasi tidak terpasang, halaman Play Store dibuka.
6. Pengguna menandai lunas setelah transfer berhasil.

Kriteria penerimaan:

- Pelunasan tersimpan di tabel `settlements`.
- Saldo bersih dan aliran utang langsung diperbarui.
- Tidak ada kredensial bank yang diminta atau disimpan.

Di luar ruang lingkup: membaca saldo, membaca mutasi, dan transfer otomatis. Fitur tersebut memerlukan agregator open banking berizin, server backend, dan persetujuan nasabah.

## 7. Alur utama

### 7.1 Pengaturan pertama

1. Buka aplikasi.
2. Masuk ke Anggota.
3. Tambahkan diri sendiri dan tandai sebagai pemilik.
4. Tambahkan teman kos.
5. Kembali ke Ringkas.

### 7.2 Membuat tagihan

1. Tekan Buat tagihan.
2. Isi judul, penanggung bayar, dan metode.
3. Isi subtotal, biaya, diskon, dan detail pembagian.
4. Tekan Hitung dan simpan.

### 7.3 Mencatat pengeluaran

1. Tekan Catat transaksi.
2. Pilih anggota dan jenis transaksi.
3. Pilih kategori, isi keterangan dan nominal.
4. Simpan.

### 7.4 Mengecek dan membayar utang

1. Buka Ringkas.
2. Lihat bagian Aliran Utang.
3. Ketuk slip utang.
4. Salin nomor dan buka aplikasi bank, atau kirim pengingat WhatsApp.
5. Tandai lunas setelah transfer berhasil.

### 7.5 Memindai struk

1. Tekan Pindai struk.
2. Arahkan kamera ke struk sampai tepinya terdeteksi.
3. Periksa item dan angka.
4. Lanjut bagi tagihan, lalu ubah pemesan setiap item.
5. Simpan.

## 8. Arsitektur informasi

Navigasi bawah:

1. **Ringkas**: kondisi finansial dan aksi cepat
2. **Tagihan**: riwayat dan pembuatan split bill
3. **Catatan**: pemasukan dan pengeluaran
4. **Anggota**: orang, pembayaran, dan budget

## 9. Arah desain

### 9.1 Intent

Pengguna membuka aplikasi beberapa menit setelah transaksi, sering sambil memegang struk atau membaca grup chat. Antarmuka harus terasa seperti buku kas yang tenang, cepat dipindai, dan tidak menghakimi.

### 9.2 Dunia visual

Gaya utama adalah neumorphism biru gelap, seperti kamar kos di malam hari yang diterangi lampu meja kebiruan.

- Satu warna permukaan untuk latar, kartu, tombol, dan input
- Cahaya biru redup dari kiri atas, bayangan pekat ke kanan bawah
- Elemen yang bisa ditekan terlihat timbul
- Elemen penerima data dan status aktif terlihat cekung
- Teks terang kebiruan agar kontras tetap kuat
- Biru azure pada aksi utama
- Merah lembut pada utang dan transaksi keluar
- Hijau mint pada transaksi masuk dan grafik
- Angka tabular yang mudah dibandingkan

### 9.3 Elemen khas

Aliran Utang memakai slip cekung yang berisi nama, arah, dan nominal seperti instruksi transfer yang dicetak ke permukaan. Elemen ini harus langsung menjawab pertanyaan utama, yaitu siapa membayar siapa.

### 9.4 Hal yang ditolak

- Gradien ungu biru dekoratif
- Glassmorphism
- Kartu metrik dengan bentuk identik
- Ilustrasi stok yang tidak membantu tugas
- Sapaan besar yang mengambil ruang
- Ikon dekoratif tanpa label
- Neumorphism pucat dengan teks abu-abu yang sulit dibaca
- Bayangan tebal yang membuat elemen terlihat melayang
- Warna berbeda untuk setiap kategori tanpa alasan

### 9.5 Token visual

| Token | Nilai | Fungsi |
|---|---|---|
| Night | `#1B2638` | Latar dan semua permukaan |
| Glow | `#304263` 60 persen | Cahaya kiri atas |
| Shade | `#05090F` 75 persen | Bayangan kanan bawah |
| Frost | `#E8EEF7` | Teks utama |
| Haze | `#93A3BD` | Metadata |
| Azure | `#2F7CF6` | Tombol aksi utama |
| Sky | `#7CB8FF` | Label, tab aktif, kursor |
| Ember | `#FF8A7A` | Utang, uang keluar, kesalahan |
| Mint | `#5FD3A4` | Uang masuk dan grafik |

| Bentuk | Radius | Kedalaman |
|---|---|---|
| Tombol | 16 dp | 4 dp |
| Input | 14 dp | 4 dp cekung |
| Kartu | 18 dp | 6 dp |
| Ringkasan utama | 24 dp | 7 dp |
| Navigasi bawah | 22 dp | 6 dp |
| Modal | 28 dp | 8 dp |

Basis jarak adalah 4 dp. Jarak antarelemen minimal 14 dp agar bayangan tidak bertabrakan. Tinggi target sentuh minimal 44 dp.

## 10. Model data

### members

| Kolom | Tipe | Aturan |
|---|---|---|
| id | INTEGER PK | Auto increment |
| name | TEXT | Wajib |
| phone | TEXT | Opsional |
| payment_info | TEXT | Opsional |
| monthly_budget | INTEGER | Default 0 |
| is_owner | INTEGER | Boolean |
| created_at | TEXT | Timestamp |

### bills

| Kolom | Tipe |
|---|---|
| id | INTEGER PK |
| title | TEXT |
| bill_date | TEXT |
| payer_id | INTEGER FK |
| method | TEXT |
| subtotal | INTEGER |
| tax_service | INTEGER |
| discount | INTEGER |
| grand_total | INTEGER |
| notes | TEXT |

### bill_shares

| Kolom | Tipe |
|---|---|
| id | INTEGER PK |
| bill_id | INTEGER FK |
| member_id | INTEGER FK |
| amount | INTEGER |
| settled | INTEGER |

### settlements

| Kolom | Tipe |
|---|---|
| id | INTEGER PK |
| from_member_id | INTEGER FK |
| to_member_id | INTEGER FK |
| amount | INTEGER |
| settled_at | TEXT |

### transactions

| Kolom | Tipe |
|---|---|
| id | INTEGER PK |
| member_id | INTEGER FK |
| kind | TEXT |
| category | TEXT |
| description | TEXT |
| amount | INTEGER |
| transaction_date | TEXT |
| source_bill_id | INTEGER FK opsional |

## 11. Kebutuhan nonfungsional

### NFR-01 Akurasi

- Seluruh uang disimpan sebagai integer Rupiah.
- Operasi persentase memakai `Decimal`.
- Jumlah porsi harus sama dengan total akhir.

### NFR-02 Performa

- Pembukaan layar target di bawah 500 ms untuk 5.000 transaksi.
- Perhitungan split dan utang target di bawah 1 detik.
- Query daftar menggunakan batas jumlah data.

### NFR-03 Offline

- Semua fitur P0 berfungsi tanpa jaringan.
- Tidak ada server database.

### NFR-04 Kompatibilitas

- Minimum Android 7, API 24.
- Target Android 15, API 35.
- Orientasi portrait.
- Arsitektur ARM 32 bit dan 64 bit.

### NFR-05 Privasi

- Data tersimpan dalam sandbox aplikasi.
- Tidak ada analytics pada MVP.
- Tidak ada data yang dikirim tanpa aksi eksplisit.

### NFR-06 Aksesibilitas

- Target sentuh minimal 44 dp.
- Informasi tidak bergantung pada warna saja.
- Label aksi memakai kata kerja.
- Kontras teks utama memenuhi target WCAG AA.

### NFR-07 Ketahanan

- Transaksi database untuk pembuatan tagihan bersifat atomik.
- Foreign key SQLite diaktifkan.
- Aplikasi menolak data pembagian tidak valid sebelum menyimpan.

## 12. Metrik keberhasilan

1. Seratus persen kasus uji pembulatan menghasilkan total yang sama.
2. Tagihan bagi rata dapat dibuat kurang dari 60 detik.
3. Pengguna dapat menjelaskan siapa membayar siapa dalam kurang dari 10 detik.
4. Aplikasi tetap dapat digunakan tanpa internet.
5. APK dapat dipasang pada perangkat API 24 atau lebih baru.
6. Ekspor Excel dapat dibuka tanpa peringatan kerusakan file.

## 13. Rencana pengembangan

### Tahap 1, fondasi

- Database SQLite
- Model anggota
- Transaksi pribadi
- Format Rupiah
- Unit test kalkulator

### Tahap 2, split bill

- Empat metode split
- Distribusi pembulatan
- Penyimpanan porsi
- Sinkronisasi ke transaksi pribadi

### Tahap 3, insight

- Dashboard
- Kategori pengeluaran
- Penyederhanaan utang
- Peringatan budget

### Tahap 4, keluaran dan Android

- Ekspor PDF
- Ekspor Excel
- Buildozer
- Uji APK pada dua versi Android
- Penanganan izin file

### Tahap 5, peningkatan

- Pemilihan pemesan item dengan sentuhan, bukan teks
- Menyimpan foto struk sebagai lampiran tagihan
- Backup dan restore database
- Kajian integrasi agregator open banking jika aplikasi berkembang menjadi layanan dengan server

## 14. Strategi pengujian

### Unit test

- Total ganjil dibagi dua dan tiga anggota
- Persentase desimal
- Persentase tidak berjumlah 100
- Nominal kustom kurang atau lebih
- Item bersama
- Diskon lebih besar dari biaya
- Rantai utang
- Anggota dengan saldo nol

### Integration test

- Membuat anggota lalu tagihan
- Tagihan menghasilkan transaksi personal
- Menutup lalu membuka database
- Ekspor dengan data kosong
- Ekspor dengan karakter Indonesia

### Uji perangkat

- Android 7 atau emulator API 24
- Android 13 atau lebih baru
- Layar kecil 360 dp
- Keyboard numerik
- Tombol back pada modal
- Instal ulang dan kehilangan data

## 15. Definition of done MVP

MVP selesai jika:

- APK debug berhasil dibuild dan dipasang.
- Empat metode split dapat disimpan.
- Total porsi selalu sama dengan total akhir.
- Anggota, transaksi, dan tagihan bertahan setelah restart.
- Dashboard menampilkan data terbaru.
- Penyederhanaan utang menghasilkan instruksi valid.
- PDF dan Excel dapat dibuat.
- Seluruh unit test lulus.
- Tidak ada crash pada alur utama.
- Batas versi dan privasi didokumentasikan.
