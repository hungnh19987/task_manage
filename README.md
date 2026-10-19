# Quản lý giao việc nội bộ

Ứng dụng web quản lý giao việc cho phòng khoảng 12 người, viết bằng Python + Streamlit, dùng PostgreSQL trên Supabase.

**Trạng thái:** Giai đoạn 1 (database, tài khoản, đăng nhập), Giai đoạn 2 (tạo, sửa, phê duyệt, phân công) Giai đoạn 3 (cập nhật tiến độ, báo cáo hoàn thành, đánh giá) và Giai đoạn 4 (Tổng quan, Báo cáo, kiểm thử phân quyền, hướng dẫn triển khai) đã hoàn thành. Nhân viên có thể tạo công việc cá nhân để trưởng phòng duyệt. Cả 5 mục giao diện đều đã hoạt động.

## Chuẩn bị Supabase

Tạo project Supabase, lấy PostgreSQL connection string trong **Connect** và đặt vào `.env` dưới tên `DATABASE_URL`. Dùng connection string có SSL (`sslmode=require`); với ứng dụng chạy liên tục, ưu tiên Session Pooler hoặc direct connection phù hợp với hạ tầng.

Khi triển khai lên Streamlit Community Cloud, kết nối GitHub repository, chọn `app.py` làm entrypoint, rồi thêm secret trong **App settings > Secrets**:

```toml
DATABASE_URL = "postgresql://..."
AUTH_COOKIE_SECRET = "...random-secret-at-least-32-characters..."
```

Tạo `AUTH_COOKIE_SECRET` bằng `python -c "import secrets; print(secrets.token_urlsafe(48))"`; giữ secret cố định giữa các lần deploy. Ứng dụng ưu tiên biến môi trường, sau đó đọc Streamlit Secrets; không đưa secrets vào source code hoặc commit `.streamlit/secrets.toml`. Đổi signing secret sẽ đăng xuất tất cả phiên cookie hiện tại. Giữ Supabase project hoạt động và dùng pooler được khuyến nghị trong dashboard cho kiểu chạy của ứng dụng.

Có thể triển khai schema trực tiếp bằng `psql`:

```bash
set -a; source .env; set +a
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/schema.sql
```

`schema.sql` là nguồn schema dùng chung; ứng dụng cũng có thể tạo schema bằng lệnh init ở dưới. Lệnh chạy lại an toàn với các bảng đã tồn tại.

SQLite cũ không được tự động chuyển dữ liệu. Hãy sao lưu database hiện tại và thực hiện chuyển dữ liệu riêng trước khi chuyển ứng dụng sang Supabase.

Xác thực dùng tài khoản PostgreSQL và hash scrypt. Cookie đăng nhập giữ token HMAC ký, chỉ gồm user ID, phiên bản xác thực và hạn dùng 30 ngày; mỗi lần tải trang, ứng dụng vẫn xác nhận tài khoản đang hoạt động và đối chiếu `auth_version` trong DB. Đổi mật khẩu thu hồi phiên cũ; đăng xuất xóa cookie. Cookie là bearer credential, vì vậy chỉ triển khai qua HTTPS và không chia sẻ token. Không cài `streamlit-authenticator`: credentials/cookie riêng và verifier bcrypt của package không khớp với tài khoản scrypt quản lý trong DB.

## 1. Cài đặt

Yêu cầu Python 3.9 trở lên.

```bash
cd task_manager
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Khởi tạo schema và tạo tài khoản quản trị

Chạy các lệnh từ thư mục gốc dự án (`task_manager/`):

```bash
python -m scripts.init_db          # tạo schema PostgreSQL (chạy lại vẫn an toàn)
python -m scripts.create_admin     # hỏi mật khẩu 2 lần, không hiện trên màn hình
```

Tuỳ chọn: `--username quantri --full-name "Quản trị hệ thống"`. Mật khẩu tối thiểu 8 ký tự. Tên đăng nhập gồm chữ thường không dấu, số, `.`, `_`, `-`.

Sau khi đăng nhập bằng ADMIN, vào mục **Tài khoản** để tạo tài khoản cho từng người, đặt lại mật khẩu, đổi vai trò, khóa/mở khóa. Mọi người dùng đã đăng nhập đều có thể vào mục **Đổi mật khẩu** để cập nhật mật khẩu của mình sau khi xác minh mật khẩu hiện tại. Hệ thống không cho tự khóa mình hoặc khóa/hạ quyền quản trị viên cuối cùng.

### Dữ liệu mẫu để kiểm thử (tuỳ chọn)

```bash
python -m scripts.seed_demo        # 1 trưởng phòng (truongphong) + 12 nhân viên (nv01 ... nv12)
```

Mật khẩu mẫu mặc định là `Demo@12345` (đổi bằng `--password`). **Chỉ dùng để thử nghiệm**, không chạy trên database thật đang vận hành.

## 3. Chạy ứng dụng

```bash
streamlit run app.py
```

Mặc định mở ở http://localhost:8501. Để các máy khác trong mạng nội bộ truy cập:

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

Lưu ý: khi tự host, đặt Streamlit sau reverse proxy có HTTPS nếu truy cập ngoài mạng nội bộ. Cookie đăng nhập tồn tại tối đa 30 ngày; đóng/mở lại trình duyệt vẫn giữ đăng nhập đến khi hết hạn, đăng xuất, đổi mật khẩu hoặc khóa tài khoản.

Ứng dụng đọc URL PostgreSQL từ `DATABASE_URL`. Có thể sao chép `.env.example` thành `.env` và điền connection string; không commit `.env` hoặc chia sẻ URL vì trong đó có thông tin đăng nhập.

## 4. Sao lưu và khôi phục

Sao lưu PostgreSQL bằng `pg_dump` (cần cài PostgreSQL client):

```bash
python -m scripts.backup_db                       # lưu vào data/backups/app_YYYYMMDD_HHMMSS.dump
python -m scripts.backup_db --keep 60 --dest /duong/dan/thu_muc_khac
```

Script lưu bản custom-format, không đưa mật khẩu lên dòng lệnh, và chỉ giữ N bản mới nhất (mặc định 30). Nên đặt lịch chạy hằng ngày, ví dụ crontab:

```
0 18 * * * cd /duong/dan/task_manager && .venv/bin/python -m scripts.backup_db
```

Nên chép định kỳ thư mục sao lưu sang máy hoặc ổ khác.

Khôi phục vào database Supabase bằng `pg_restore` (có thể dùng `--clean --if-exists` khi chủ ý thay thế schema/dữ liệu hiện có):

```bash
set -a; source .env; set +a
pg_restore --no-owner --no-privileges --dbname "$DATABASE_URL" data/backups/app_YYYYMMDD_HHMMSS.dump
```

## 5. Kiểm thử

```bash
pip install -r requirements-dev.txt
python -m pytest
```

Chạy bộ kiểm thử hiện có bằng `python -m pytest`. Với database Supabase, cần cấu hình `DATABASE_URL` cho môi trường chạy kiểm thử.

## 6. Quy trình công việc (Giai đoạn 2)

```
TEAM:   Bản nháp -> Chờ phê duyệt -> Đang thực hiện        (hoặc Bị từ chối -> sửa -> gửi lại)
DIRECT: Đang thực hiện ngay (trưởng phòng giao, không cần duyệt)
PERSONAL: Chờ phê duyệt -> Đang thực hiện (nhân viên tự giao đúng một phần việc cho mình)
```

| Thao tác | Ai được làm |
|---|---|
| Tạo công việc nhóm (TEAM) | Trưởng phòng, nhân viên |
| Giao việc trực tiếp (DIRECT) | Trưởng phòng |
| Tạo công việc cá nhân (PERSONAL) | Nhân viên; tự phân công cho mình và gửi duyệt ngay |
| Sửa thông tin khi Nháp / Bị từ chối | Người đề xuất, trưởng phòng |
| Sửa thông tin khi Đang thực hiện | Trưởng phòng |
| Gửi phê duyệt | Người đề xuất, trưởng phòng (cần có chủ trì và ít nhất 1 phần việc) |
| Duyệt / Từ chối (bắt buộc ghi lý do) | Trưởng phòng |
| Thêm/sửa/xóa phần việc khi Nháp / Bị từ chối | Người đề xuất, người chủ trì, trưởng phòng |
| Thêm/sửa/xóa phần việc khi Đang thực hiện | Người chủ trì, trưởng phòng |
| Xem danh sách, chi tiết, nhật ký | Mọi người dùng |

Quy tắc đáng chú ý:
- Mỗi người chỉ có 1 phần việc trong một công việc. Người chủ trì cũng có thể nhận một phần việc.
- **Nhập bảng khi phân công nhiều người cùng một loại việc:** ở tab "Phần việc" > "Thêm phần việc", chọn "Nhập bảng (nhiều người)". Nhập nội dung và đơn vị một lần, rồi trong bảng tích chọn người nhận và điền khối lượng riêng của từng người (có thể chọn sẵn tất cả). Hệ thống tạo mỗi người một phần việc riêng, có nhật ký riêng, và là một lô duy nhất: nếu một dòng sai (ví dụ người đó đã có phần việc) thì không dòng nào được lưu.
- ADMIN không được giao việc, không làm chủ trì hay thành viên (chỉ quản lý tài khoản).
- Hạn hoàn thành không được ở quá khứ khi tạo hoặc đổi hạn. Công việc chưa báo cáo mà quá hạn được đánh dấu ⚠.
- Không xóa được phần việc đã có tiến độ hoặc báo cáo kết quả.
- Khi đang chờ phê duyệt, không ai sửa được công việc hay phân công; muốn sửa phải để trưởng phòng từ chối, người đề xuất sửa rồi gửi lại.
- Mọi thay đổi quan trọng (tạo, sửa, gửi, duyệt, từ chối, thêm/sửa/xóa phần việc) đều ghi vào `task_logs` cùng transaction với thay đổi đó.

## 7. Tiến độ, báo cáo và đánh giá (Giai đoạn 3)

```
Đang thực hiện -> Đã báo cáo, chờ đánh giá -> Đạt
                                           -> Không đạt -> (trưởng phòng mở lại) -> Đang thực hiện
```

| Thao tác | Ai được làm | Khi nào |
|---|---|---|
| Cập nhật khối lượng đã hoàn thành (hoặc % nếu không có khối lượng giao) và báo cáo kết quả phần việc nhóm | Người chủ trì, cho mọi thành viên | Đang thực hiện |
| Cập nhật phần việc của công việc cá nhân / giao trực tiếp | Chính người thực hiện | Đang thực hiện |
| Nhận xét phần việc của thành viên | Người chủ trì của công việc đó, trưởng phòng | Đang thực hiện hoặc chờ đánh giá |
| Báo cáo hoàn thành (công việc nhóm) | Người chủ trì | Đang thực hiện, khi mọi thành viên đã 100% và có báo cáo |
| Đánh giá Đạt / Không đạt | Trưởng phòng | Đã báo cáo |
| Mở lại công việc "Không đạt" | Trưởng phòng (bắt buộc ghi lý do) | Không đạt |

Quy tắc đáng chú ý:
- **Tiến độ công việc nhóm do người chủ trì cập nhật thay cho các thành viên.** Trong chi tiết công việc, chủ trì nhập tiến độ và báo cáo kết quả riêng cho từng thành viên; thành viên không tự cập nhật phần việc nhóm. Với công việc cá nhân/giao trực tiếp, người thực hiện vẫn tự cập nhật phần việc của mình.
- **Tiến độ tính theo khối lượng tuyệt đối.** Với phần việc có khối lượng giao, người có quyền cập nhật chỉ nhập *khối lượng đã hoàn thành* (ví dụ 12 trên tổng 20 trạm); chương trình tự tính tiến độ % = đã hoàn thành / được giao (12/20 = 60%) và hiển thị ngay khi nhập. Số liệu gốc (khối lượng đã hoàn thành) được lưu và ghi nhật ký.
  - Được nhập số thập phân. Được làm vượt khối lượng giao; tiến độ vẫn tối đa 100%.
  - Tiến độ chỉ là 100% khi đã làm đủ khối lượng giao; trước đó tối đa 99% (ví dụ 996/1000 là 99%, không làm tròn thành 100%).
  - Nếu người chủ trì hoặc trưởng phòng sửa khối lượng giao, tiến độ % tự tính lại theo khối lượng đã hoàn thành. Nếu bỏ khối lượng giao, phần việc chuyển sang nhập % trực tiếp và giữ nguyên % hiện có.
  - Phần việc **không có** khối lượng giao thì vẫn nhập tiến độ trực tiếp theo % (số nguyên 0-100).
- Khi tiến độ đạt 100% bắt buộc có báo cáo kết quả. Người chủ trì được điều chỉnh tiến độ/báo cáo của thành viên nếu cần làm lại.
- Công việc nhóm (TEAM): người chủ trì báo cáo hoàn thành kèm báo cáo tổng hợp. Chỉ báo cáo được khi **mọi** thành viên đã 100% và có báo cáo kết quả.
- Công việc giao trực tiếp (DIRECT) chỉ giao cho **một người**, người đó là **chủ trì** và có đúng một phần việc. Hệ thống **tự động** chuyển sang "Đã báo cáo, chờ đánh giá" ngay khi người được giao hoàn thành (100% kèm báo cáo kết quả), không cần báo cáo tổng hợp riêng.
  - Không thêm/xóa người và không đổi người được giao (cần giao người khác thì tạo công việc mới). Trưởng phòng vẫn sửa được tên, mô tả, hạn, nội dung và khối lượng phần việc.
  - Người được giao chỉ cập nhật tiến độ phần việc của mình; không tự sửa phân công hay tự nhận xét mình. Nhận xét phần việc do trưởng phòng thực hiện.
  - **Công việc cá nhân (PERSONAL)** cũng chỉ có một phần việc do chính nhân viên đề xuất thực hiện. Khác với DIRECT, PERSONAL phải được trưởng phòng phê duyệt trước khi bắt đầu; sau khi duyệt, tiến độ, báo cáo tự động và đánh giá giống DIRECT. Nếu bị từ chối, nhân viên có thể sửa thông tin/phần việc rồi gửi duyệt lại.
  - Việc DIRECT nằm ở mục "Phần việc của tôi" của người được giao (không lặp lại ở "Công việc tôi chủ trì", mục này chỉ dành cho việc nhóm). Trong báo cáo, người được giao vẫn được tính là người chủ trì.
  - Công việc DIRECT tạo từ các phiên bản trước (có nhiều người) vẫn xem và làm việc bình thường; khi nâng cấp, việc có đúng một người thực hiện được tự gán người đó làm chủ trì.
- Sau khi báo cáo, không ai đổi được tiến độ nữa; trưởng phòng và chủ trì vẫn nhận xét được.
- Đánh giá "Không đạt" bắt buộc có nhận xét. "Đạt" có thể để trống nhận xét. Đánh giá không thể sửa; sai thì chỉ có cách "Không đạt" rồi mở lại.
- Mở lại đưa công việc về "Đang thực hiện" và xóa kết quả đánh giá, báo cáo tổng hợp, thời điểm hoàn thành khỏi công việc. Mọi lần đánh giá và mở lại vẫn còn nguyên trong nhật ký. Với việc DIRECT sau khi mở lại, thành viên cập nhật hoặc gửi lại phần việc của mình để công việc tự báo cáo lần nữa.
- Trang **Công việc của tôi**: phần việc của tôi (cập nhật ngay tại đây nếu được quyền; với việc nhóm, tiến độ do chủ trì nhập ở chi tiết công việc), việc tôi chủ trì, việc tôi đề xuất còn ở bước nháp/chờ duyệt/bị từ chối. Trang **Phê duyệt** có hai tab: Chờ phê duyệt và Chờ đánh giá.
- Người dùng khác vẫn xem được tiến độ, báo cáo, nhận xét và nhật ký của mọi công việc (STAFF xem tất cả công việc của phòng).

## 7b. Tổng quan và Báo cáo (Giai đoạn 4)

- **Tổng quan**: số việc đang thực hiện, quá hạn, chờ phê duyệt, chờ đánh giá, Đạt/Không đạt; biểu đồ số việc theo trạng thái (có bảng số liệu kèm theo); tiến độ trung bình; danh sách quá hạn và sắp đến hạn 7 ngày; tải công việc từng người. Mọi vai trò đều xem được.
- **Báo cáo**: chọn kỳ (theo **hạn hoàn thành** của công việc) hoặc khoảng ngày tùy chọn; lọc theo trạng thái, loại, người liên quan; xem danh sách công việc và thống kê theo người; tải CSV (mã hóa UTF-8 có BOM, mở trực tiếp bằng Excel).
- Quá hạn = công việc chưa kết thúc (chưa báo cáo/đánh giá) có hạn trước hôm nay (giờ Việt Nam). Công việc có hạn đúng hôm nay chưa tính là quá hạn.
- Tỷ lệ đạt = Đạt / (Đạt + Không đạt), chỉ tính việc đã được đánh giá.
- CSV chặn công thức độc hại: ô bắt đầu bằng `=`, `+`, `-`, `@` được thêm dấu `'` phía trước.
- Báo cáo không cộng khối lượng giữa các phần việc vì đơn vị khác nhau.

## 7c. Triển khai chính thức

Các file mẫu nằm trong thư mục `deploy/` và `.streamlit/config.toml`. Ví dụ trên Linux (Ubuntu), cài vào `/opt/task_manager`:

1. **Cài đặt**
   ```bash
   sudo mkdir -p /opt/task_manager
   # chép mã nguồn vào /opt/task_manager, rồi:
   cd /opt/task_manager
   sudo bash scripts/install_service.sh
   sudo -u taskmgr .venv/bin/python -m scripts.create_admin
   ```
    Script cài dependencies, tạo `.env` từ `.env.example` nếu chưa có, cài và bật service systemd. Điền `DATABASE_URL` Supabase vào `/opt/task_manager/.env` trước khi chạy script; script không ghi đè `.env` hay tự tạo mật khẩu quản trị. Cài thêm `postgresql-client` để có `pg_dump` cho sao lưu.
   Cổng cấu hình trong `/opt/task_manager/.env`:
   ```dotenv
   STREAMLIT_SERVER_PORT=8501
   STREAMLIT_SERVER_ADDRESS=127.0.0.1
   ```
   Sửa cổng trong file này rồi chạy `sudo systemctl restart taskmanager` để áp dụng. Mặc định ứng dụng chỉ lắng nghe `127.0.0.1` để dùng cùng nginx reverse proxy. Nếu cần truy cập trực tiếp từ mạng nội bộ, đặt `STREAMLIT_SERVER_ADDRESS=0.0.0.0` và giới hạn cổng đã chọn bằng tường lửa cho các máy/mạng tin cậy.
2. **Chạy như dịch vụ**: script cài `deploy/taskmanager.service` vào `/etc/systemd/system/`, bật service và khởi động ứng dụng. Xem trạng thái bằng `sudo systemctl status taskmanager`; nhật ký bằng `sudo journalctl -u taskmanager`.
3. **HTTPS**: dùng `deploy/nginx-taskmanager.conf` (đã có cấu hình WebSocket cần cho Streamlit). Sửa tên miền và đường dẫn chứng chỉ; nếu đổi `STREAMLIT_SERVER_PORT`, cập nhật cổng trong `proxy_pass` cho trùng. Không mở cổng Streamlit ra ngoài; chỉ mở 443 (và 80 để chuyển hướng) trên tường lửa, ví dụ `sudo ufw allow 443/tcp`.
4. **Sao lưu tự động**: chép `deploy/backup-cron.example` vào `/etc/cron.d/taskmanager-backup`. Các bản dump nằm trong `data/backups`; nên chép sang máy/ổ khác và thỉnh thoảng thử khôi phục.
5. **Tài khoản**: tạo tài khoản thật từ mục Tài khoản bằng quản trị viên. Nếu đã chạy `seed_demo` để thử, đổi/khóa toàn bộ tài khoản mẫu (mật khẩu mẫu `Demo@12345` là công khai). Với môi trường thật, nên khởi tạo database mới.
6. **Nâng cấp phiên bản**: sao lưu, thay mã nguồn, `pip install -r requirements.txt`, `python -m scripts.init_db` để áp dụng schema idempotent, rồi `sudo systemctl restart taskmanager`. Những thay đổi schema phá hủy/tái cấu trúc dữ liệu cần có migration PostgreSQL riêng.
7. **Khôi phục sự cố**: dùng `pg_restore --no-owner --no-privileges --dbname "$DATABASE_URL" <file.dump>` như phần trên; không chép dump vào thư mục dữ liệu ứng dụng.
8. **Quên mật khẩu**: quản trị viên đặt lại ở mục Tài khoản. Nếu mất cả tài khoản quản trị: `python -m scripts.create_admin` tạo thêm quản trị viên mới.

Lưu ý bảo mật còn lại: ứng dụng chưa có giới hạn số lần đăng nhập sai. Nếu cho phép truy cập công khai, cần bổ sung rate limiting ở lớp edge/proxy hoặc chuyển sang nhà cung cấp danh tính có kiểm soát đăng nhập; Streamlit Community Cloud không dùng nginx cấu hình kèm dự án.

## 8. Cấu trúc thư mục

```
app.py            điểm vào Streamlit: đăng nhập + điều hướng
config.py         hằng số và cấu hình môi trường
core/
  database.py     kết nối PostgreSQL, schema, transaction
  auth.py         băm mật khẩu, đăng nhập, quản lý tài khoản
  permissions.py  kiểm tra quyền ở tầng nghiệp vụ
  task_service.py nghiệp vụ công việc: tạo, sửa, gửi/duyệt/từ chối, phân công, truy vấn
  report_service.py số liệu tổng quan, báo cáo theo kỳ/người, xuất CSV
  log_service.py  ghi/đọc task_logs (chỉ thêm, không sửa/xóa)
  timeutil.py     lưu UTC, hiển thị giờ Việt Nam
supabase/
  schema.sql      schema PostgreSQL triển khai bằng psql
ui/               các trang giao diện (không chứa SQL hay quy tắc quyền)
  task_list.py, task_detail.py, approvals.py, my_tasks.py, overview.py, reports.py, accounts.py, login.py, components.py
scripts/          init_db, create_admin, seed_demo, backup_db
deploy/           mẫu systemd, nginx (HTTPS), cron sao lưu
.streamlit/       config.toml (headless, tắt thu thập thống kê)
tests/            kiểm thử tự động
data/             backups PostgreSQL (không đưa vào git)
```

## 9. Ghi chú thiết kế

- Chỉ 4 bảng: `users`, `tasks`, `task_members`, `task_logs`. Vai trò, loại công việc, trạng thái là hằng số trong `config.py`, được ép bằng ràng buộc CHECK trong database.
- Mỗi người chỉ có 1 phần việc trong một công việc (UNIQUE `task_id, user_id`).
- `task_logs` được bảo vệ bằng trigger: mọi lệnh UPDATE/DELETE đều bị từ chối. Giao diện cũng không có chức năng sửa/xóa nhật ký. Cột `task_logs.member_id` chỉ là số tham chiếu, cố ý không có khóa ngoại, để vẫn xóa được phần việc mà giữ nguyên nhật ký.
- Thời gian lưu dạng UTC, hiển thị theo giờ Việt Nam.
- Chưa có giới hạn số lần đăng nhập sai; nếu triển khai công khai trên Streamlit Community Cloud, cần thêm rate limiting hoặc một lớp xác thực/edge protection phù hợp.
