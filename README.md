# Claude Token Meter

[![tests](https://github.com/phuocs0n/claude-token-meter/actions/workflows/test.yml/badge.svg)](https://github.com/phuocs0n/claude-token-meter/actions/workflows/test.yml)
[![release](https://img.shields.io/github/v/release/phuocs0n/claude-token-meter)](https://github.com/phuocs0n/claude-token-meter/releases/latest)

Công cụ mã nguồn mở để xem **bạn đã dùng những model Claude nào**, **đã dùng bao nhiêu token**, và **ước lượng sẽ dùng bao nhiêu token** nếu giữ tốc độ hiện tại. Viết bằng Python thuần, không cần thư viện ngoài, không cần API key, chạy hoàn toàn trên máy bạn.

*(English below.)*

## Tải app (không cần cài Python)

Vào trang [**Releases**](https://github.com/phuocs0n/claude-token-meter/releases/latest) và tải file cho máy của bạn:

| Máy | File | Cách cài |
|---|---|---|
| Windows 10/11 (64-bit) | `ClaudeTokenMeter-Setup-<phiên bản>.exe` | Chạy file, bấm **Next** đến hết. App cài cho riêng tài khoản của bạn, không cần quyền admin. Lần sau mở từ Start menu: **Claude Token Meter**. |
| Windows, bản không cần cài | `ClaudeTokenMeter-<phiên bản>-windows-x64-portable.zip` | Giải nén, chạy `ClaudeTokenMeter.exe`. |
| macOS (chip Apple M1 trở lên) | `ClaudeTokenMeter-<phiên bản>-macos-arm64.zip` | Giải nén, kéo `ClaudeTokenMeter.app` vào **Applications**. |
| Linux (x64) | `ClaudeTokenMeter-<phiên bản>-linux-x64.tar.gz` | `tar xzf ClaudeTokenMeter-*.tar.gz` rồi chạy `./ClaudeTokenMeter/ClaudeTokenMeter`. |

Khi mở app, bạn thấy một cửa sổ nhỏ gồm token hôm nay, tốc độ 7 ngày, dự báo 30 ngày tới và phiên 5 giờ hiện tại. Dashboard đầy đủ mở trong cửa sổ riêng: Windows dùng Edge ở chế độ app, macOS và Linux dùng trình duyệt mặc định. Số liệu tự cập nhật mỗi phút. Đóng cửa sổ nhỏ là tắt app. Nút **English / Tiếng Việt** đổi ngôn ngữ và được nhớ cho lần sau.

App chưa được ký số (chứng chỉ ký số tốn phí), nên lần đầu mở:

- **Windows** có thể hiện "Windows protected your PC": bấm **More info → Run anyway**.
- **macOS** báo app từ nhà phát triển không xác định: chuột phải vào app → **Open** → **Open**. Nếu vẫn bị chặn, chạy `xattr -dr com.apple.quarantine /Applications/ClaudeTokenMeter.app`.

Gỡ cài đặt trên Windows: **Settings → Apps → Installed apps → Claude Token Meter → Uninstall**.

Muốn dùng lệnh trong terminal (`token-meter ...`), hoặc dùng máy Mac chip Intel: chạy từ mã nguồn theo phần [Cách chạy](#cách-chạy) bên dưới.

## Tính năng

- **Lịch sử model**: mỗi model dùng lần đầu / gần nhất, số ngày dùng, số request, và các lần bạn đổi model chính.
- **Lượng token đã dùng**: input, output, ghi cache, đọc cache; theo model, theo ngày / tuần / tháng, theo dự án và theo phiên.
- **Dự báo**: token và chi phí cho 24 giờ, 7 ngày, 30 ngày tới và đến hết tháng, tính theo tốc độ 7 ngày gần nhất, đối chiếu với tốc độ 30 ngày và đường xu hướng.
- **Cửa sổ 5 giờ**: lượng đã dùng trong cửa sổ hiện tại, tốc độ token/phút, dự kiến khi hết cửa sổ, so với cửa sổ lớn nhất trước đây.
- **Chi phí ước tính** theo bảng giá API công khai (có thể thay bằng bảng giá của bạn).
- **Dashboard HTML**: một file duy nhất, chạy offline, có biểu đồ, bộ lọc thời gian, giao diện sáng/tối, tiếng Việt/English. Có chế độ `serve` tự cập nhật mỗi 60 giây.
- **App cho Windows, macOS, Linux**: cài như phần mềm bình thường, không cần Python.
- Xuất **JSON** cho mọi lệnh để dùng trong script khác.

## Dữ liệu lấy từ đâu

Claude Code (CLI, tab Code trong app Claude desktop, tiện ích VS Code / JetBrains, Agent SDK) lưu mỗi phiên làm việc thành một file `.jsonl`. Mỗi câu trả lời của model có trường `usage` ghi số token đã tính. Công cụ đọc các thư mục:

- `~/.claude/projects/` (Windows: `C:\Users\<tên>\.claude\projects\`)
- `~/.config/claude/projects/`
- `$CLAUDE_CONFIG_DIR/projects/` nếu bạn đặt biến môi trường này

Công cụ **chỉ đọc** các file này, không sửa và không gửi dữ liệu đi đâu.

> Lưu ý: các cuộc trò chuyện trên claude.ai (web, tab Chat của app) không lưu số token trên máy, nên không đo được bằng công cụ này.

## Cách chạy

### Bước 1. Cài Python 3.11 trở lên

Kiểm tra bằng:

```bash
python --version
```

Nếu máy chưa có Python hoặc phiên bản thấp hơn 3.11:

- **Windows**: chạy `winget install Python.Python.3.13`, hoặc tải từ [python.org](https://www.python.org/downloads/) và nhớ tick **Add python.exe to PATH** khi cài.
- **macOS**: `brew install python`
- **Linux**: dùng trình quản lý gói của bản phân phối, ví dụ `sudo apt install python3` (khi đó gõ `python3` thay cho `python`).

Bạn cũng cần đã dùng Claude Code (CLI, tab Code của app Claude desktop, hoặc tiện ích VS Code / JetBrains) ít nhất một lần để máy có log.

### Bước 2. Tải mã nguồn

```bash
git clone https://github.com/phuocs0n/claude-token-meter.git
cd claude-token-meter
```

Nếu không có `git`: trên trang GitHub của dự án bấm **Code → Download ZIP**, giải nén, rồi mở terminal trong thư mục `claude-token-meter-main`.

### Bước 3. Chạy

**Cách A: chạy ngay, không cần cài.** Đứng trong thư mục dự án và gõ:

```bash
python -m token_meter              # tổng quan
python -m token_meter forecast     # dự báo
python -m token_meter dashboard    # mở dashboard trong trình duyệt
```

**Cách B: cài thành lệnh `token-meter`** để gõ ở bất kỳ thư mục nào:

```bash
pip install .
token-meter
```

Hoặc cài thẳng từ GitHub mà không cần tải mã nguồn về trước:

```bash
pip install git+https://github.com/phuocs0n/claude-token-meter.git
```

Hai cách cho kết quả như nhau: `python -m token_meter <lệnh>` và `token-meter <lệnh>` là một.

### Bước 4. Xem dashboard

```bash
token-meter dashboard              # tạo token-meter-dashboard.html trong thư mục hiện tại rồi mở trình duyệt
token-meter dashboard --out D:\bao-cao.html --no-open   # lưu chỗ khác, không tự mở
token-meter serve                  # dashboard trực tiếp tại http://127.0.0.1:8765, tự cập nhật mỗi 60 giây
```

Với `serve`, giữ cửa sổ terminal mở trong lúc xem; bấm **Ctrl+C** để dừng.

Cài theo Cách B còn có lệnh `token-meter-app`: mở app có cửa sổ nhỏ giống bản tải về, không cần giữ terminal.

> File dashboard chứa số liệu sử dụng và đường dẫn các dự án của bạn. Đừng đưa nó lên mạng nếu không muốn người khác thấy.

### Cập nhật phiên bản mới

```bash
git pull
pip install .        # chỉ cần nếu bạn đã cài theo Cách B
```

### Gặp lỗi?

| Thông báo | Cách xử lý |
|---|---|
| `'token-meter' is not recognized…` / `command not found` | Thư mục `Scripts` của Python chưa có trong PATH. Dùng `python -m token_meter` thay thế, hoặc cài lại Python và tick **Add python.exe to PATH**. |
| `No module named token_meter` | Bạn đang ở ngoài thư mục dự án mà chưa cài. `cd` vào thư mục dự án, hoặc cài theo Cách B. |
| `Không tìm thấy dữ liệu sử dụng` | Máy chưa có log Claude Code, hoặc log nằm chỗ khác: chỉ đường dẫn bằng `--path "D:\đường\dẫn\projects"`. |
| `Không mở được cổng 8765` khi chạy `serve` | Cổng đang bận, thường do một cửa sổ `serve` khác vẫn đang chạy. Đóng cửa sổ đó, hoặc dùng cổng khác: `token-meter serve --port 9000`. |
| Bảng hiển thị ký tự lạ `?` | Dùng Windows Terminal hoặc PowerShell thay cho cmd cũ, hoặc thêm `--lang en`. |

## Các lệnh

```bash
token-meter                  # tổng quan: token theo loại, theo model, dự báo nhanh, cửa sổ 5 giờ
token-meter models           # lịch sử model và các lần đổi model
token-meter daily            # theo ngày   (weekly / monthly: theo tuần / tháng)
token-meter forecast         # dự báo chi tiết
token-meter blocks           # các cửa sổ 5 giờ gần đây
token-meter projects         # theo dự án (thư mục làm việc)
token-meter sessions         # các phiên tốn nhiều token nhất
token-meter dashboard        # tạo token-meter-dashboard.html và mở trong trình duyệt
token-meter serve            # dashboard trực tiếp tại http://127.0.0.1:8765, tự cập nhật
```

Tuỳ chọn dùng được với mọi lệnh:

| Tuỳ chọn | Ý nghĩa |
|---|---|
| `--days 30` | chỉ lấy 30 ngày gần nhất |
| `--since 2026-11-01` / `--until 2026-11-30` | lọc theo ngày |
| `--model opus` | chỉ model có tên chứa chuỗi này (lặp lại được) |
| `--project my-app` | chỉ dự án có đường dẫn chứa chuỗi này |
| `--window 14` | tính tốc độ dự báo theo 14 ngày gần nhất (mặc định 7) |
| `--path DIR` | đọc thư mục hoặc file `.jsonl` khác (lặp lại được) |
| `--pricing prices.json` | dùng bảng giá riêng |
| `--json` | in JSON |
| `--full` | in số đầy đủ (1,234,567) thay vì 1.23M |
| `--lang en` | tiếng Anh (hoặc đặt `TOKEN_METER_LANG=en`) |

Ví dụ kết quả (số liệu minh hoạ):

```
DỰ BÁO (theo tốc độ 7 ngày gần nhất)
  Tốc độ: 12.40M token/ngày · $9.85/ngày · 95 request/ngày
              Theo 7 ngày  Chi phí*  Theo 30 ngày  Chi phí*  Theo xu hướng
 ───────────  ───────────  ────────  ────────────  ────────  ─────────────
 24 giờ tới        12.40M     $9.85        10.10M     $8.02         13.20M
 7 ngày tới        86.80M    $68.95        70.70M    $56.14         95.60M
 30 ngày tới      372.00M   $295.50       303.00M   $240.60        425.10M
  Hết tháng 2026-11: 410.30M ≈ $325.70  (đã dùng 330.90M, còn 6.4 ngày)

PHIÊN 5 GIỜ HIỆN TẠI
  13:00 → 18:00 · còn 3h12m · đã dùng 9.80M ($7.90)
  Tốc độ 92.30K/phút → dự kiến 27.50M ($22.20) khi hết phiên
```

## Cách tính

- **Gộp bản ghi trùng.** Khi trả lời dạng streaming, một câu trả lời được ghi nhiều lần vào log. Các dòng có cùng `message.id` + `requestId` được gộp lại, giữ bản đầy đủ nhất.
- **Tổng token** = input + output + ghi cache + đọc cache. Đọc cache thường chiếm phần lớn số token (ngữ cảnh được dùng lại giữa các lượt) nhưng giá chỉ bằng khoảng 1/10 đến 1/20 input thường.
- **Dự báo.** Tốc độ = tổng token trong *N* ngày gần nhất chia cho *N* (mặc định *N* = 7; nếu lịch sử ngắn hơn thì chia cho số ngày thực có). Dự báo *k* ngày = tốc độ × *k*. Bảng dự báo đặt cạnh nhau ba cách tính: theo tốc độ *N* ngày, theo tốc độ 30 ngày, và theo đường hồi quy tuyến tính qua tổng token mỗi ngày của tối đa 30 ngày đã kết thúc. Ba con số chênh nhau nhiều nghĩa là thói quen dùng đang thay đổi.
- **Đến hết tháng** = token đã dùng từ đầu tháng + tốc độ × số ngày còn lại.
- **Cửa sổ 5 giờ.** Một cửa sổ mở từ đầu giờ của request đầu tiên và kéo dài 5 giờ; request đầu tiên sau khi cửa sổ đóng mở cửa sổ mới. Tốc độ trong cửa sổ = token đã dùng ÷ số phút từ request đầu tiên đến bây giờ. Đây là ước lượng gần đúng cách các gói Claude giới hạn lượng dùng; Anthropic không công bố giới hạn token chính xác, nên công cụ so sánh với cửa sổ lớn nhất của chính bạn.
- **Chi phí** là chi phí tương đương nếu trả theo API (USD / 1 triệu token): input, output, ghi cache 5 phút (1,25 × input), ghi cache 1 giờ (2 × input), đọc cache (giá riêng của model, mặc định 0,1 × input), chế độ fast (× 2). Gói Pro / Max / Team không tính tiền theo token, nên con số này chỉ để so sánh.

### Bảng giá riêng

Bảng giá mặc định nằm trong [`token_meter/pricing.py`](token_meter/pricing.py) (giá công khai tháng 11/2026). Để thêm hoặc sửa giá, tạo file JSON rồi dùng `--pricing`:

```json
{
  "claude-opus-5-5": {"input": 4, "output": 20, "cache_read": 0.2},
  "my-custom-model": {"input": 1, "output": 5}
}
```

Khoá là tiền tố tên model; tên dài hơn được ưu tiên, nên `claude-opus-4-1` khớp trước `claude-opus-4`. Tiền tố kiểu Bedrock (`us.anthropic.`) và hậu tố ngày (`-20250805`) được bỏ qua khi so khớp.

## Phát triển

```bash
python -m unittest discover -s tests -v
```

Cấu trúc mã:

| File | Nội dung |
|---|---|
| `token_meter/loader.py` | tìm và đọc file `.jsonl`, gộp bản ghi trùng, hỗ trợ đường dẫn dài trên Windows |
| `token_meter/pricing.py` | bảng giá và tính chi phí |
| `token_meter/analysis.py` | tổng hợp theo model / thời gian / dự án / phiên, cửa sổ 5 giờ |
| `token_meter/forecast.py` | tốc độ, xu hướng, dự báo |
| `token_meter/report.py`, `i18n.py` | bảng chữ cho terminal, tiếng Việt / English |
| `token_meter/dashboard.py`, `dashboard.html` | dashboard HTML và server trực tiếp |
| `token_meter/cli.py` | các lệnh |
| `token_meter/app.py` | app desktop: cửa sổ nhỏ (tkinter) chạy dashboard ở nền |
| `packaging/` | build app bằng PyInstaller, bộ cài Windows (Inno Setup), biểu tượng |

### Tự build app

```bash
pip install pyinstaller pillow
python packaging/build.py                        # tạo dist/ClaudeTokenMeter (macOS: dist/ClaudeTokenMeter.app) rồi tự kiểm tra
python packaging/build.py --installer --package  # Windows: thêm bộ cài Setup .exe (cần Inno Setup 6) và các file phát hành trong dist/release
```

Phát hành phiên bản mới: tăng `__version__` trong `token_meter/__init__.py`, commit, rồi đẩy tag, ví dụ `git tag v0.2.0` và `git push origin v0.2.0`. Workflow [release.yml](.github/workflows/release.yml) build app trên Windows, macOS, Linux và tạo GitHub Release kèm các file tải về.

Đóng góp rất được hoan nghênh: mở issue hoặc pull request.

---

## English

**Claude Token Meter** shows which Claude models you have used, how many tokens they took, and how many you will use at your current rate. It reads the JSONL session logs that Claude Code (CLI, the Code tab of the Claude desktop app, IDE extensions, Agent SDK) writes to `~/.claude/projects/`. Pure Python 3.11+, no dependencies, no API key, nothing leaves your machine.

**Desktop app** (no Python needed): download it from [Releases](https://github.com/phuocs0n/claude-token-meter/releases/latest): `ClaudeTokenMeter-Setup-<version>.exe` for Windows 10/11 (per-user install, no admin rights), the `-windows-x64-portable.zip`, `-macos-arm64.zip` (Apple Silicon) or `-linux-x64.tar.gz`. The app shows today's tokens, the 7-day rate, the 30-day forecast and the current 5-hour window in a small window, and opens the full dashboard in its own window. Closing the small window quits. The builds are not code-signed: on Windows choose **More info → Run anyway** in SmartScreen; on macOS right-click the app → **Open** the first time. To build it yourself: `pip install pyinstaller pillow` and `python packaging/build.py`.

**How to run from source** (Python 3.11+):

```bash
git clone https://github.com/phuocs0n/claude-token-meter.git
cd claude-token-meter
python -m token_meter --lang en  # run without installing, from the project folder
pip install .                    # or install the token-meter command
```

Or install straight from GitHub: `pip install git+https://github.com/phuocs0n/claude-token-meter.git`. If `token-meter` is not found after installing, Python's `Scripts` folder is not on your PATH: use `python -m token_meter` instead.

```bash
token-meter --lang en            # overview
token-meter models --lang en     # model history and model switches
token-meter forecast --lang en   # next 24h / 7d / 30d / end of month, current 5-hour window
token-meter dashboard            # offline HTML dashboard (has its own language switch)
token-meter serve                # live dashboard on http://127.0.0.1:8765
```

Every command accepts `--days`, `--since`, `--until`, `--model`, `--project`, `--window`, `--path`, `--pricing`, `--json` and `--full`. The forecast uses the average daily use of the last 7 days (`--window`), shown next to the 30-day rate and a linear trend. Costs are API-equivalent estimates; subscription plans are not billed per token.

## Giấy phép / License

[MIT](LICENSE)
