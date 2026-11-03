# KosSplit Android

KosSplit adalah aplikasi Android lokal untuk membagi tagihan, mencatat pengeluaran, memantau arus kas, dan menyederhanakan utang penghuni kos. Aplikasi ditulis dengan Python dan Kivy. Data disimpan di SQLite pada perangkat, tanpa server dan tanpa akun.

## Yang sudah tersedia

- Manajemen anggota, info pembayaran, dan budget bulanan
- Pencatatan pemasukan dan pengeluaran
- Catatan otomatis dikelompokkan per bulan dan tahun tanpa menghapus data lama
- Setiap bulan tampil sebagai menu berisi jumlah pengeluaran, pemasukan, dan totalnya
- Tagihan dengan metode bagi rata
- Tagihan dengan nominal kustom
- Tagihan dengan persentase
- Tagihan per item, termasuk item yang dibagi beberapa anggota
- Distribusi pajak, layanan, ongkir, dan diskon secara proporsional
- Pembulatan deterministik tanpa kehilangan satu Rupiah
- Penyederhanaan utang dengan greedy matching
- Ringkasan arus kas dan kategori pengeluaran
- Ekspor Excel berisi sheet Ringkasan per bulan, Transaksi, dan Tagihan dengan label Indonesia dan format Rupiah
- Ekspor PDF bulan berjalan berisi ringkasan, daftar transaksi, dan tagihan patungan
- Lokasi dan nama file ekspor bisa dipilih sendiri, lalu file bisa langsung dibuka
- Database SQLite lokal
- Pindai struk dengan kamera, galeri, atau teks tempelan
- Parser struk Python untuk item, subtotal, pajak, layanan, diskon, dan total
- Tagihan per item otomatis terisi dari hasil pindai
- Slip utang yang bisa diketuk: salin nomor rekening lalu buka aplikasi bank atau e-wallet
- Pengingat pembayaran via WhatsApp
- Pencatatan pelunasan utang

## Periode catatan

Setiap catatan menyimpan `transaction_date` dalam format tanggal ISO. Layar **Catatan**
menampilkan setiap bulan sebagai menu tersendiri, dikelompokkan per tahun dan diurutkan
dari yang terbaru. Setiap menu menunjukkan berapa pengeluaran dan pemasukan di bulan itu
beserta totalnya, lalu bisa diketuk untuk membuka daftar transaksinya. Bulan berjalan
selalu tampil paling atas dan terbuka otomatis. Tidak ada filter bulan atau tahun yang
perlu dipilih manual.

KosSplit membaca tanggal sistem perangkat saat aplikasi dibuka, dilanjutkan, dan setiap
30 detik selama aplikasi terbuka, sehingga bulan baru langsung muncul tanpa membuka ulang aplikasi. Android tidak menyediakan dan tidak mewajibkan izin khusus untuk
membaca waktu sistem, sehingga aplikasi tidak meminta izin tambahan. Data lama tidak
dihapus saat pergantian bulan.

## Batas versi 0.2

- KosSplit tidak terhubung langsung ke akun bank. Aplikasi tidak membaca saldo, mutasi, atau melakukan transfer otomatis. Lihat bagian Koneksi bank.
- Pemindai kamera memerlukan Google Play services. Jika tidak tersedia, gunakan galeri atau tempel teks.
- Hasil OCR selalu perlu diperiksa sebelum disimpan, terutama struk yang kusut, buram, atau berhuruf miring.
- Belum ada sinkronisasi cloud, login, atau penggunaan bersama antarperangkat.

## Memilih lokasi ekspor

Tombol **Ekspor Excel** dan **Ekspor PDF** ada di layar Catatan. Laporan dibuat dulu di penyimpanan privat aplikasi, baru disalin ke lokasi pilihan, jadi kalau pembuatan laporan gagal tidak ada file kosong yang tertinggal.

- **Android:** terbuka layar "Simpan sebagai" bawaan Android. Pilih folder seperti Download, Dokumen, atau Google Drive, ubah nama file jika perlu, lalu ketuk Simpan. Cara ini tidak memerlukan izin penyimpanan. Jika nama sudah dipakai, Android menambahkan angka, misalnya `(1)`, dan nama akhirnya ditampilkan. Ketuk **Buka file** untuk membukanya di Google Sheets, Excel, atau pembaca PDF.
- **Komputer:** pilih folder dan nama file di dalam aplikasi. Folder terakhir yang dipakai diingat untuk ekspor berikutnya. Jika file dengan nama yang sama sudah ada, aplikasi meminta konfirmasi sebelum menimpanya.

Kodenya ada di `kossplit/file_saver.py`.

## Status bar, navigation bar, dan keyboard

`android.api = 35` membuat Android 15 menggambar aplikasi layar penuh, sampai ke belakang jam, sinyal, baterai, dan tombol navigasi. KosSplit menanganinya di `kossplit/platform_bridge.py` dan `kossplit/layout.py`:

- **Halaman utama** diberi jarak atas dan bawah sesuai tinggi status bar, navigation bar, dan notch yang dilaporkan Android. HP lama yang sudah menyisakan ruang sendiri tidak mendapat jarak dobel.
- **Kalau ukuran belum tersedia** saat aplikasi baru dibuka, aplikasi mencoba lagi beberapa kali. Kalau tetap gagal, dipakai ukuran bar dari tema Android, atau 24dp dan 48dp sebagai cadangan.
- **Keyboard** diukur langsung dari Android, karena `Window.keyboard_height` milik Kivy selalu 0 di bootstrap SDL2. Saat mengetik, popup form mengecil di atas keyboard dan field yang aktif otomatis digulir supaya terlihat.
- **Menu pilihan** dibuka ke atas atau ke bawah tanpa masuk ke area status bar, navigation bar, atau keyboard.

Setelah build, uji di HP Android 15 dengan navigasi gestur dan dengan 3 tombol. Buka "Periksa hasil", lalu ketuk field **Total di struk** untuk memastikan field tetap terlihat di atas keyboard.

## Bagaimana Python dan Java bekerja sama

| Bagian | Bahasa | Lokasi |
|---|---|---|
| UI, database, kalkulator, parser struk, pembayaran | Python | `main.py`, `kossplit/` |
| Kamera pemindai dokumen | Java, Google ML Kit | dipanggil dari `kossplit/receipt_scanner.py` |
| Pembacaan teks pada gambar | Java, Google ML Kit | dipanggil dari `kossplit/receipt_scanner.py` |
| Membuka aplikasi bank, WhatsApp, Play Store | Android Intent | dipanggil dari `kossplit/platform_bridge.py` |

Python memanggil library Java melalui Pyjnius. Tidak ada file Java atau Kotlin yang perlu ditulis sendiri. Buildozer mengunduh library ML Kit melalui baris `android.gradle_dependencies` di `buildozer.spec`.

## Pindai struk

Alurnya:

1. Tekan **Pindai struk** di Ringkas atau Tagihan.
2. Pilih **Buka kamera pemindai**. Google ML Kit Document Scanner mendeteksi tepi struk, meluruskan, dan memperjelas gambar.
3. ML Kit Text Recognition membaca teks langsung di ponsel, tanpa internet dan tanpa server.
4. `receipt_parser.py` menyusun ulang baris struk dari posisi teks, lalu mengenali item, subtotal, PPN, PB1, service, ongkir, diskon, dan total.
5. Layar **Periksa hasil** menampilkan setiap item sebagai kartu tersendiri berisi nama dan harga. Semua nominal tampil utuh tanpa perlu digeser, dan menyentuh nominal langsung memilih seluruh angka sehingga bisa diganti. Item bisa ditambah atau dihapus.
6. **Lanjut bagi tagihan** membuka tagihan per item. Setiap item awalnya dibagi ke semua anggota, ganti nama di akhir baris sesuai pemesan.

Jika total struk tidak sama dengan jumlah item, selisihnya otomatis dimasukkan ke biaya tambahan atau diskon sehingga total tagihan tetap sama persis dengan struk.

### Format nominal yang dikenali

Parser di `kossplit/money.py` dipakai bersama oleh OCR dan semua input nominal:

| Tertulis di struk | Dibaca sebagai |
|---|---|
| `48.000` atau `48,000` | Rp48.000 |
| `Rp48.000` atau `IDR 48.000,00` | Rp48.000 |
| `48.000,00` atau `48.000.00` | Rp48.000, dua digit terakhir dianggap sen |
| `48.000,` atau `48.000,-` | Rp48.000 |
| `48k` atau `48,5k` | Rp48.000 atau Rp48.500 |

Setiap field nominal memakai format IDR: awalan `Rp`, titik ribuan otomatis saat mengetik, dan akhiran `,00`. Mengetik `1500000` langsung tampil sebagai `Rp 1.500.000,00`. Nilai tetap disimpan sebagai Rupiah bulat.

### Uji OCR di komputer

```bash
pip install -r requirements-ocr.txt
```

Pasang juga aplikasi Tesseract OCR:

- Ubuntu: `sudo apt install tesseract-ocr tesseract-ocr-ind`
- macOS: `brew install tesseract tesseract-lang`
- Windows: pasang installer Tesseract dari UB Mannheim, lalu tambahkan folder instalasinya ke PATH

Tanpa Tesseract, gunakan kolom **Tempel teks struk** untuk menguji parser.

## Koneksi bank

Yang sudah tersedia:

- Saat menambah anggota, pilih bank atau e-wallet dan isi nomor rekening.
- Di Ringkas, ketuk slip utang seperti **Bima → Ayu**.
- **Salin nomor dan buka BCA mobile** menyalin nomor rekening, lalu membuka aplikasi resmi bank atau e-wallet penerima.
- Jika aplikasi belum terpasang, halaman Play Store aplikasi tersebut dibuka.
- **Ingatkan via WhatsApp** membuka WhatsApp dengan pesan tagihan yang sudah terisi.
- **Tandai sudah lunas** mencatat pelunasan dan memperbarui aliran utang.

Aplikasi yang dikenali: BCA mobile, blu by BCA Digital, Livin' by Mandiri, BRImo, BNI Mobile, GoPay, OVO, DANA, dan ShopeePay. Nama paket aplikasi berada di `kossplit/payments.py` dan dapat ditambah.

Mengapa tidak login langsung ke bank:

- Bank di Indonesia tidak menyediakan API publik untuk aplikasi pribadi.
- Membaca saldo atau mutasi memerlukan agregator open banking berizin, seperti Brick atau Ayoconnect, beserta server backend, perjanjian bisnis, dan persetujuan nasabah.
- Menyimpan kredensial bank di ponsel melanggar ketentuan bank dan berisiko tinggi.
- Pendekatan KosSplit tetap aman: transfer selalu dikonfirmasi pengguna di aplikasi resmi bank.

## Menjalankan di komputer

Gunakan Python 3.10 sampai 3.13 versi 64-bit. Kivy 2.3.1 belum mendukung Python 3.14, jadi jangan
memakai versi Python terbaru.

### Linux atau macOS

```bash
cd kossplit_android
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
python main.py
```

### Windows untuk pengembangan UI

```powershell
cd kossplit_android
py -3.13 -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
python main.py
```

Jika `pip` mengunduh `Kivy-2.3.1.tar.gz` lalu gagal dengan pesan
`kivy-deps.angle~=0.4.0`, berarti venv dibuat dengan Python yang terlalu baru. Pasang
Python 3.13 atau 3.12 dari python.org, hapus folder `.venv`, lalu ulangi langkah di atas.
Perintah `py -0` menampilkan semua versi Python yang terpasang.

Build APK sebaiknya dilakukan di Linux. Pengguna Windows dapat memakai WSL2 Ubuntu.

## Menguji logika

```bash
cd kossplit_android
pytest
```

Tes mencakup pembulatan Rupiah, empat metode split, penyederhanaan utang, penyimpanan tagihan, pelunasan, parser struk, dan deteksi bank.

## Build APK debug

### 1. Siapkan Ubuntu

Di Ubuntu atau WSL2:

```bash
sudo apt update
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip python3-venv \
  autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev \
  libtinfo6 cmake libffi-dev libssl-dev
```

### 2. Siapkan virtual environment

```bash
cd kossplit_android
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install buildozer cython==0.29.36
```

### 3. Build APK

```bash
buildozer android debug
```

Build pertama dapat memerlukan waktu 20 sampai 60 menit karena Android SDK, NDK, dependensi Python, dan library ML Kit akan diunduh. Jika sebelumnya sudah pernah build versi 0.1, jalankan `buildozer android clean` terlebih dahulu agar dependensi Gradle baru ikut dipasang. APK akan tersedia di folder `bin/`.

### 4. Pasang ke perangkat

Aktifkan Developer Options dan USB Debugging pada Android, lalu jalankan:

```bash
buildozer android deploy run
```

Alternatifnya, salin APK dari folder `bin/` ke ponsel lalu buka file tersebut. Izinkan pemasangan dari sumber yang digunakan ketika Android memintanya.

## Build APK release

```bash
buildozer android release
```

Hasil release harus ditandatangani sebelum dapat dibagikan melalui Play Store. Untuk tugas kuliah atau demo langsung, APK debug biasanya sudah cukup.

## Cara memakai empat metode split

### Bagi rata

Isi subtotal, pajak atau biaya, serta diskon. Aplikasi membagi total akhir kepada seluruh anggota dan menangani sisa pembulatan.

### Nominal kustom

Isi detail dalam satu atau beberapa baris:

```text
Ayu=60000, Bima=40000
```

Jumlah nominal harus tepat sama dengan total akhir.

### Persentase

```text
Ayu=60, Bima=40
```

Jumlah persentase harus tepat 100.

### Per item

Gunakan satu baris untuk setiap item:

```text
Nasi goreng|25000|Ayu
Es teh|10000|Bima
Kentang|18000|Ayu+Bima
```

Formatnya adalah `nama item|harga|anggota`. Tanda `+` berarti satu item dibagi rata kepada beberapa anggota. Jumlah harga item harus sama dengan subtotal.

## Struktur proyek

```text
kossplit_android/
├── main.py
├── buildozer.spec
├── requirements.txt
├── requirements-dev.txt
├── requirements-ocr.txt
├── pyproject.toml
├── PRD.md
├── README.md
├── kossplit/
│   ├── calculator.py
│   ├── database.py
│   ├── exporter.py
│   ├── money.py
│   ├── payments.py
│   ├── platform_bridge.py
│   ├── receipt_parser.py
│   └── receipt_scanner.py
└── tests/
    ├── test_calculator.py
    ├── test_database.py
    ├── test_payments.py
    └── test_receipt_parser.py
```

## Keputusan visual

KosSplit memakai neumorphism biru gelap:

- Semua permukaan memakai satu warna night blue `#1B2638`
- Kedalaman dibuat dari cahaya biru redup di kiri atas dan bayangan pekat di kanan bawah, bukan garis tepi
- Tombol dan kartu timbul, lalu tertekan ke dalam saat disentuh
- Input, chip nominal, slip utang, dan tab aktif dibuat cekung
- Biru azure `#2F7CF6` menjadi satu-satunya warna aksi utama, biru langit `#7CB8FF` untuk label dan tab aktif
- Merah lembut `#FF8A7A` hanya untuk utang, uang keluar, dan pesan kesalahan
- Hijau mint `#5FD3A4` untuk uang masuk dan isi grafik
- Teks utama `#E8EEF7` dan metadata `#93A3BD` menjaga kontras tetap terbaca di latar gelap

Bayangan digambar dengan `kivy.graphics.BoxShadow`, termasuk mode `inset`, sehingga Kivy 2.3 atau lebih baru diperlukan.

## Keamanan dan privasi

- Semua data tersimpan lokal pada sandbox aplikasi.
- Aplikasi tidak mengirim data ke server.
- Nomor telepon dan rekening tidak dienkripsi pada versi 0.1.
- Jangan menyimpan PIN, kata sandi, atau kode OTP pada kolom info pembayaran.
- Backup database perlu dilakukan secara manual sebelum aplikasi dihapus.
