# x-flask-starter


---

## 🧪 Başlıq və Rate-limit nişanı

* **“X + Flask Minimal UI”** başlığı → bu səhifənin mini interfeys olduğunu göstərir.
* **Qırmızı nişan (`rate-limit: 123s`)** → Əgər X API sənə **429 Too Many Requests** (çox sorğu göndərdin) cavabını qaytarıbsa, burada gerisayım çıxır. Gerisayım bitmədən yeni sorğu göndərə bilməzsən; düymələr kilidlənir. Bu səni boş yerə kotanı sərf etməkdən qoruyur.

---

## 👤 İstifadəçi zaman xətti bölməsi

* **İstifadəçi adı qutusu** → Məs: `CryptoMelih` və ya `KapitalBankOJSC`.

* **Limit qutusu** → Neçə tweet gətiriləcəyini göstərir (1–100).

* **next\_token qutusu** → Səhifələmə açarıdır; əvvəlki cavabdan gələn `meta.next_token` dəyərini bura yazsan **növbəti səhifəni** gətirir.

* **retweet/reply daxil et checkbox**

  * İşarələnmiş → retweet və cavabları **daxil edir**.
  * Boş → retweet və cavabları **çıxarır** (standart davranış).

* **Getir düyməsi** → İstifadəçi profilini və seçilmiş parametrlərə görə zaman xəttini gətirir.

* **Daha Çox düyməsi** → Növbəti səhifəni (next\_token ilə) gətirir.

* **CSV endir düyməsi** → İstifadəçinin zaman xəttini CSV faylı kimi endirir. `pages=N` parametri ilə bir neçə səhifəni tək faylda toplaya bilərsən.

---

## 🔎 Son Axtarış bölməsi

* **Sorğu qutusu** → X API axtarış parametrini yazırsan. Nümunələr:

  * `from:nasa moon` → NASA-nın “moon” keçən tweetləri
  * `bitcoin lang:tr` → Türk dilində bitcoin tweetləri
  * `"openai gpt-5"` → tam ifadə axtarışı

* **Limit qutusu** → Neçə tweet gətiriləcəyini göstərir.

* **next\_token qutusu** → Növbəti səhifə üçün istifadə olunur.

* **retweet/reply daxil et checkbox** → Eyni qayda ilə retweet və cavabların daxil edilib-edilməməsini idarə edir.

* **Ara düyməsi** → Axtarışı başladır.

* **Daha Çox düyməsi** → Axtarışın davam səhifəsini gətirir.

* **CSV endir düyməsi** → Axtarış nəticələrini CSV kimi endirir.

---

## 📊 JSON çıxışı qutusu

* **“JSON çıxışını göstər/gizlə”** açılan düymə → arxa plandakı xam JSON məlumatını görmək üçün.
* Burada X API-nin qaytardığı bütün tweet metadatası görünür (id, mətn, author\_id, public\_metrics, media linkləri və s.).
* İnkişaf etdirici/test üçün faydalıdır: xam məlumatı görürsən, kartlarda görünməyən sahələri yoxlaya bilirsən.

---

## 📦 Nə tip məlumat alırıq?

* **User** → profil məlumatları (id, username, name, bio, izləyici sayı, izlədikləri, ümumi tweet sayı və s.).
* **Tweets** → tweet mətni, yaradılma vaxtı, dil, public\_metrics (like, retweet, reply, quote, bookmark, baxış sayı), media linkləri, mentionlar, hashtaglər.
* **Meta** → `newest_id`, `oldest_id`, `result_count`, `next_token`.
* **Rate-limit** → API kotasının nə vaxt sıfırlanacağını göstərir.

---

  
