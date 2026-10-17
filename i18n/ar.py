"""النصوص العربية للواجهة. المفاتيح يجب أن تطابق ``i18n/en.py`` بالضبط.

الجزء الأول: رسائل الحماية، لوحات المفاتيح، أوامر المالك، أدوات المالك.
"""

from __future__ import annotations

STRINGS: dict[str, str] = {
    'gate.user.start': '👋 أرسل رسالتك هنا للتحدث مع المساعد الشخصي.',
    'gate.user.start_paid': '⭐ سعر الرسالة {stars} نجمة. متبقي لك {free} رسائل مجانية. أرسل نص رسالتك لتظهر فاتورة الدفع؛ لن يتم الرد قبل الدفع بعد انتهاء المجاني.',

    "gate.user.payment_unavailable": '⚠️ الرسائل المدفوعة مفعّلة لكن السعر لم يُضبط بعد. حاول لاحقًا.',
    'ai.key_source.shared': 'مفتاح مركزي من المالك',
    'kbd.gate.sub_toggle': '🔒 تشغيل/إيقاف الاشتراك الإجباري',
    'gate.user.unavailable': '⚠️ إرسال الرسائل متوقف مؤقتًا لحين ضبط الاشتراك الإجباري. حاول لاحقًا.',
    'gate.user.text_required': '⭐ يلزم الدفع قبل الرد. أرسل رسالتك كنص لإظهار فاتورة النجوم.',
    'gate.sub.bad': 'أرسل @username أو رابط قناة عامة مثل https://t.me/channel. للقناة الخاصة: -1001234567890 | اسم القناة | https://t.me/+رابط_الدعوة',

    # =========================================================================
    # security.py
    # =========================================================================
    "sec.non_owner_notice": (
        "👋 ده <b>مساعد تيليجرام مُدار</b>، وما بيردّش هنا مباشرة.\n\n"
        "لو عايز توصل لصاحب الحساب، كلّمه من خلال حساب Telegram Business بتاعه. "
        "وصاحب البوت بيربطه من <b>إعدادات تيليجرام ← Telegram Business ← Chatbots</b>."
    ),
    "sec.claim_notice": (
        "🔐 المساعد لسه مفعّلش.\n\n"
        "لو إنت صاحب البوت: افتح نافذة الأوامر اللي البوت شغال فيها وابعت "
        "<code>/start &lt;claim-code&gt;</code> بالكود اللي ظهر هناك."
    ),
    "sec.claimed": (
        "✅ <b>مبوك! إنت دلوقتي صاحب البوت.</b>\n\n"
        "الخطوة الجاية: /setup بيمشّيك خطوة بخطوة لربط البوت بحساب Telegram Business، "
        "و /ai لاختيار مزوّد الذكاء الاصطناعي، و /faq لإضافة ردودك، و /mode لتحديد "
        "طريقة الرد.\n\n"
        "ولو مش عايز تربطه بحساب Business أصلاً: البوت بيرد على الرسائل الخاصة اللي "
        "توصله هو نفسه بمجرد ما تشغّل الوضع (/mode). شوف /help ← «الرسائل الخاصة»."
    ),
    "sec.not_authorized": "غير مصرّح لك.",

    # =========================================================================
    # keyboards.py
    # =========================================================================
    "kbd.mode.auto": "🟢 رد تلقائي",
    "kbd.mode.draft": "📝 مسودة (بموافقتك)",
    "kbd.mode.off": "🔴 متوقف",
    "kbd.mode_row": "{label} — اضغط للتغيير",
    "kbd.panel.status": "📊 الحالة",
    "kbd.panel.help": "❓ المساعدة",
    "kbd.panel.ai": "🤖 مزوّد الذكاء",
    "kbd.panel.faq": "💬 ردود جاهزة",
    "kbd.panel.kb": "📚 قاعدة المعرفة",
    "kbd.panel.settings": "⚙️ الإعدادات",
    "kbd.panel.pending": "📨 موافقات معلّقة",
    "kbd.panel.mem_clear": "🧹 مسح الذاكرة",
    "kbd.panel.setup": "🚀 دليل الإعداد",
    "kbd.panel.health": "❤️ فحص النظام",
    "kbd.back": "« رجوع",
    "kbd.close": "✖ إغلاق",
    "kbd.prev": "« السابق",
    "kbd.next": "التالي »",
    "kbd.confirm.yes": "✅ نعم",
    "kbd.confirm.no": "✖ لا",

    "kbd.ai.free_providers": "🆓 المزوّدين المجانيين (بدون بطاقة)",
    "kbd.ai.change_provider": "🔁 تغيير المزوّد",
    "kbd.ai.change_model": "🧠 تغيير الموديل",
    "kbd.ai.load_models": "🔄 تحميل الموديلات من المزوّد",
    "kbd.ai.add_key": "🔑 إضافة / تحديث مفتاح API",
    "kbd.ai.test": "🧪 اختبار الاتصال",
    "kbd.ai.remove_key": "🗑 حذف مفتاح API",
    "kbd.ai.show_every": "🔁 اعرض كل المزوّدين",
    "kbd.ai.only_free": "🆓 المجانيين بس",
    "kbd.ai.switch": "🆓 التبديل إلى {label}",
    "kbd.ai.switch_nokey": "🆓 التبديل إلى {label} (بدون مفتاح)",
    "kbd.ai.resend_key": "🔑 ابعت نفس المفتاح تاني",
    "kbd.ai.back_menu": "« رجوع لقائمة الذكاء",
    "kbd.ai.type_model": "✏️ اكتب اسم موديل تاني",
    "kbd.ai.send_key": "🔑 ابعت مفتاح API الآن",
    "kbd.ai.send_key_optional": "🔑 ابعت مفتاح API (اختياري)",
    "kbd.ai.choose_model": "🧠 اختيار الموديل",
    "kbd.ai.set_base_url": "🌐 ضبط Base URL",
    "kbd.ai.free_instead": "🆓 مزوّدين مجانيين بدل ده",

    "kbd.faq.add": "➕ إضافة رد سريع",
    "kbd.faq.list": "📃 عرض / حذف",
    "kbd.faq.search": "🔍 بحث",
    "kbd.faq.export": "⬇️ تصدير (JSON)",
    "kbd.faq.clear": "🗑 مسح الكل",
    "kbd.faq.entry": "🗑 {state}{title}",

    "kbd.kb.add": "➕ إضافة نص",
    "kbd.kb.upload": "📎 رفع ملف",
    "kbd.kb.search": "🔍 بحث",
    "kbd.kb.list": "📃 عرض العناصر",
    "kbd.kb.clear": "🗑 مسح الكل",
    "kbd.kb.untitled": "بدون عنوان",
    "kbd.kb.item": "🗑 #{id} {title} ({count})",

    "kbd.chat.pause": "⏸ إيقاف الرد التلقائي",
    "kbd.chat.resume": "▶️ استئناف الرد التلقائي",
    "kbd.apr.send": "✅ إرسال",
    "kbd.apr.edit": "✏️ تعديل",
    "kbd.apr.reject": "🚫 رفض",
    "kbd.apr.pause": "⏸ إيقاف المحادثة",

    # =========================================================================
    # owner_commands.py
    # =========================================================================
    "own.ai.ready": "جاهز ✅",
    "own.ai.not_ready": "مش مُعدّ ⚠️ — افتح /ai",
    "own.ai.not_ready_short": "مش مُعدّ ⚠️",
    "own.start": (
        "👋 <b>Alfiqi Ai — مساعد تيليجرام</b>\n\n"
        "الوضع: <b>{mode}</b> · الذكاء: <b>{backend}</b> ({ai_state})\n\n"
        "الإعداد في ٣ خطوات: /setup · /ai · /faq"
    ),
    "own.help": (
        "🤖 <b>Alfiqi Ai — مساعد تيليجرام</b>\n\n"
        "البوت بيردّ على الرسائل الخاصة اللي بتوصل له: إمّا رسائل عملاء حساب "
        "Telegram Business (لو ربطته من تيليجرام ← Business ← Chatbots)، وإمّا رسائل أي "
        "حد بيكتب للبوت نفسه على الخاص. الناس ما بتكلّمش البوت مباشرة: هي بتكتب، وهو "
        "بيردّ.\n\n"
        "<b>الإعداد من الأول</b>\n"
        "١. @BotFather ← /mybots ← بوتك ← Bot Settings ← <b>Business Mode</b> "
        "(في نسخ بتسمى Secretary Mode) ← Turn on — وده مطلوب بس لو عايز البوت يرد على "
        "رسائل حساب Telegram Business بتاعك.\n"
        "٢. تيليجرام ← <b>الإعدادات ← Telegram Business ← Chatbots</b> ← اكتب يوزر "
        "البوت ← فعّل <b>«Allow bot to reply to messages»</b> ← اختر المحادثات ← "
        "احفظ.\n"
        "٣. هنا: /ai لاختيار الذكاء، و /faq لردودك، و /mode لتحديد الوضع.\n"
        "شرح مصوّر خطوة بخطوة: /setup\n\n"
        "<b>الرسائل الخاصة (من غير حساب Business)</b>\n"
        "أي حد يبعت للبوت رسالة خاصة، البوت يردّ عليه بالذكاء الاصطناعي طالما الوضع "
        "شغّال، وإنت بيجيلك إشعار بكل رسالة. شغّله/اقفله بـ /direct أو من "
        "/settings ← الردود. و /takeover &lt;chat_id&gt; بيوقف البوت عن محادثة معينة "
        "تفضل إنت اللي تردّ فيها.\n\n"
        "<b>أوامر يومية</b>\n"
        "/mode — رد تلقائي · مسودة (موافقتك قبل الإرسال) · متوقف\n"
        "/status — الحالة كاملة\n"
        "/health — فحوصات (التوكن، الذكاء، الاتصال، التخزين)\n"
        "/chats — آخر المحادثات · /chat &lt;id&gt; — نص المحادثة\n"
        "/reply &lt;chat_id&gt; &lt;النص&gt; — ترد إنت بنفسك\n"
        "/takeover &lt;id&gt; · /handback &lt;id&gt; — إيقاف / استئناف الذكاء لمحادثة\n"
        "/pause_chat &lt;id&gt; · /resume_chat &lt;id&gt; — نفس الحاجة لأي محادثة موقوفة\n"
        "/stats — عدد العملاء والرسائل والردود\n"
        "/export — ملف نسخة احتياطية (الإعدادات + الردود الجاهزة)\n\n"
        "<b>إعداد الذكاء الاصطناعي</b>\n"
        "/ai — المزوّد، مفتاح API، الموديل، اختبار · /aitest — اختبار سريع\n"
        "/freeai — المزوّدين المجانيين (بدون بطاقة ولا رصيد)\n"
        "/aimodel &lt;name&gt; — تحديد موديل · /instructions — تعليمات دائمة\n\n"
        "<b>الردود</b>\n"
        "/faq — قائمة الردود الجاهزة (ردود حرفية بتتبعت في الحال)\n"
        "/faq_add كلمة1, كلمة2 :: الرد الحرفي\n"
        "/kb — قاعدة المعرفة · /kb_add · /kb_upload · /kb_search · /kb_list\n\n"
        "<b>تعليم البوت (الرسائل الخاصة)</b>\n"
        "/rules — تعليماتك بكلامك، وانت اللي تعتمد المسودة\n"
        "/unanswered — الأسئلة اللي معرفش يرد عليها، وإجابتك بتتعلم\n"
        "/resources — مواقع / منصات / جروبات تيليجرام يبحث فيها\n"
        "/gate — اشتراك إجباري في قنواتك، ورسائل مدفوعة بنجوم تيليجرام "
        "(والسعر انت اللي تحدده)\n\n"
        "<b>اللوحة والتنظيف</b>\n"
        "/start — لوحة التحكم · /settings — كل الإعدادات\n"
        "/language — تبديل لغة واجهة البوت (العربية / English)\n"
        "/approval_on · /approval_off · /auto_on · /auto_off\n"
        "/memory_clear — نسيان المحادثات · /reset — إلغاء الموافقات والإيقافات\n"
        "/cancel — إلغاء طلب معلّق\n\n"
        "<i>تدخّل المالك:</i> أول ما تردّ إنت بنفسك على عميل (من التطبيق أو بـ /reply)، "
        "البوت بيوقف الرد التلقائي على المحادثة دي لمدة."
    ),
    "own.status.title": "📊 <b>الحالة</b>",
    "own.status.reply_mode": "وضع الرد: <b>{mode}</b>",
    "own.status.switches": (
        "مفتاح الرد التلقائي: <b>{auto}</b> · الموافقة قبل الإرسال: <b>{approval}</b>"
    ),
    "own.status.ai": "الذكاء الاصطناعي: <b>{state}</b>",
    "own.status.key_url": "   هات مفتاح من هنا: {url}",
    "own.status.freeai_hint": (
        "   💡 /freeai — مزوّدين بدون بطاقة بنكية وبدون رصيد."
    ),
    "own.status.direct": "الرسائل الخاصة (للبوت): <b>{state}</b>",
    "own.status.direct_on": "بيردّ ✅",
    "own.status.direct_off": "مقفول — شغّله بـ /direct",
    "own.status.direct_hint": (
        "   الرسائل الخاصة ما بتحتاجش ربط Telegram Business: أي حد يبعت للبوت بياخد "
        "رد طالما الوضع شغّال."
    ),
    "own.status.conn_none": (
        "حسابات Telegram Business المربوطة: <b>مفيش</b> — اربط البوت من "
        "تيليجرام ← الإعدادات ← Business ← Chatbots."
    ),
    "own.status.conn_count": "حسابات Telegram Business المربوطة: <b>{count}</b>",
    "own.status.conn_row": "  • المالك <code>{owner}</code> · {state} · {reply}",
    "own.status.conn_enabled": "مفعّل",
    "own.status.conn_disabled": "موقوف",
    "own.status.conn_can_reply": "يقدر يرد",
    "own.status.conn_read_only": "قراءة بس ⚠️",
    "own.status.paused": "محادثات موقوفة: <b>{count}</b>",
    "own.status.pending": "موافقات معلّقة: <b>{count}</b>",
    "own.status.kb": "قاعدة المعرفة: <b>{items}</b> عنصر / {chunks} جزء",
    "own.status.faq": "الردود الجاهزة: <b>{count}</b>",
    "own.status.health_hint": "<i>اعمل /health لفحص كامل.</i>",

    "own.connections.none": (
        "مفيش حساب Telegram Business مربوط لسه.\n\n"
        "تيليجرام ← الإعدادات ← Telegram Business ← Chatbots ← ضيف البوت ← اسمح له "
        "بالرد. الشرح الكامل: /setup\n\n"
        "ومش مستخدم Telegram Business؟ الرسائل الخاصة اللي توصل البوت بيترد عليها "
        "كمان — شوف /direct."
    ),
    "own.connections.title": "🔗 <b>حسابات Telegram Business</b>",
    "own.connections.row_id": "• المعرّف <code>{id}</code>",
    "own.connections.row_owner": "  المالك: <code>{owner}</code>",
    "own.connections.row_state": "  مفعّل: <b>{enabled}</b> · يقدر يرد: <b>{can_reply}</b>",
    "own.connections.row_updated": "  آخر تحديث: {updated}",

    "own.key_removed": (
        "تم حذف مفتاح {provider}. الردود بالذكاء الاصطناعي هتفضل متوقفة لحد ما تضيف "
        "مفتاح تاني من /ai."
    ),
    "own.toggle": "{label}: <b>{state}</b>\nوضع الرد: <b>{mode}</b>",
    "own.label.auto": "الردود التلقائية",
    "own.label.approval": "الموافقة قبل الإرسال",

    "own.mem_clear_ask": "أمسح <b>كل</b> ذاكرة المحادثات؟",
    "own.mem_clear_ask_plain": "أمسح كل ذاكرة المحادثات؟",
    "own.pause.ask": "ابعت رقم المحادثة اللي عايز توقفها، أو /cancel.",
    "own.resume.ask": "ابعت رقم المحادثة اللي عايز تستأنفها، أو /cancel.",
    "own.pause.bad_id": "«{raw}» مش رقم محادثة صحيح.",
    "own.pause.no_connection": (
        "معرفتش أحدد حساب Telegram Business بتاع المحادثة دي "
        "(مفيش رسائل لسه، أو فيه أكتر من حساب مربوط)."
    ),
    "own.pause.paused": "⏸ تم إيقاف المحادثة <code>{chat_id}</code>.",
    "own.pause.resumed": "▶️ تم استئناف <code>{chat_id}</code>.",
    "own.pause.not_paused": "المحادثة دي مش موقوفة أصلاً",
    "own.reset_ask": (
        "أعمل إعادة ضبط للحالات المؤقتة؟ ده بيلغي كل <b>الموافقات المعلّقة</b>، "
        "وبيمسح <b>الإيقافات</b>، وبيلغي أي إدخال معلّق. الإعدادات وقاعدة المعرفة "
        "والسجل مش هيتأثروا."
    ),
    "own.cancelled": "تم الإلغاء. ✖",
    "own.instructions.title": (
        "📝 <b>تعليمات إضافية</b> — بتتضاف دايمًا لتعليمات النظام بتاعة الذكاء "
        "الاصطناعي (بتأثر على كل رد ومن أي مزوّد):\n\n"
        "{current}\n\n"
        "للضبط: <code>/instructions &lt;النص&gt;</code>\n"
        "مثال: <code>/instructions رد دايمًا بالعامية المصرية وباختصار.</code>\n"
        "للمسح: <code>/instructions clear</code>\n\n"
        "<i>ملاحظة: اللغة والنبرة والشخصية ليهم صفوف خاصة في /settings ← الشخصية.</i>"
    ),
    "own.instructions.none": "<i>(مفيش)</i>",
    "own.instructions.cleared": "تم مسح التعليمات الإضافية. ✖",
    "own.instructions.updated": (
        "✅ تم تحديث التعليمات الإضافية. هتتطبق على كل الردود من دلوقتي."
    ),

    "own.admin.usage": (
        "الاستخدام: <code>/admin &lt;user_id&gt;</code> للإضافة، "
        "<code>/admin remove &lt;user_id&gt;</code> للحذف، أو <code>/admin list</code>."
    ),
    "own.admin.list_title": "المشرفون المفوّضون:",
    "own.admin.list_none": "(مفيش)",
    "own.admin.bad_id": "ابعت رقم مستخدم تيليجرام صحيح وموجب.",
    "own.admin.primary_kept": "صاحب البوت الأساسي ما ينفعش يتحذف كمشرف مفوّض.",
    "own.admin.not_changed": "المشرف <code>{user_id}</code> ما اتعملوش {verb}.",
    "own.admin.changed": (
        "✅ المشرف <code>{user_id}</code> اتعمله {verb}. لازم يربط حساب Telegram "
        "Business بتاعه قبل ما يدير مساعده."
    ),
    "own.admin.added": "إضافة",
    "own.admin.removed": "حذف",
    "own.fallback": (
        "مش فاهم الأمر ده. استخدم /start للوحة التحكم أو /help لقائمة الأوامر."
    ),

    "own.panel.home": "👋 <b>لوحة التحكم</b>",
    "own.panel.choose_mode": "اختر وضع الرد",
    "own.panel.mode_set": "الوضع: {mode}",
    "own.panel.toggle": "{label} {state}",
    "own.confirm.cancelled": "تم الإلغاء.",
    "own.confirm.done": "تم.",
    "own.confirm.done_ok": "تم ✅",
    "own.confirm.kb_cleared": "تم مسح قاعدة المعرفة.",
    "own.confirm.faq_cleared": "تم مسح الردود الجاهزة ({count} رد).",
    "own.confirm.key_removed": "تم حذف مفتاح {provider}.",
    "own.confirm.mem_cleared": "تم مسح ذاكرة المحادثات ({count} سطر).",
    "own.confirm.reset": (
        "تمت إعادة الضبط: {cancelled} موافقة اتلغت، و {paused} إيقاف اتشال."
    ),

    # =========================================================================
    # handlers/owner_tools.py
    # =========================================================================
    "tool.mode.auto": "🟢 <b>رد تلقائي</b> — البوت بيردّ على العملاء في الحال.",
    "tool.mode.draft": (
        "📝 <b>وضع المسودة</b> — البوت بيكتب الرد ويستنى ضغطة منك "
        "(إرسال / تعديل / رفض). ما بيوصلش للعميل حاجة من غير موافقتك."
    ),
    "tool.mode.off": "🔴 <b>متوقف</b> — البوت ساكت، وبيجيلك إشعار بكل رسالة.",
    "tool.mode.set": "{text}\n\nالوضع: <b>{mode}</b>",
    "tool.mode.current": (
        "الوضع الحالي: {text}\n\n"
        "اختر وضع (أو استخدم <code>/mode auto|draft|off</code>):"
    ),
    "tool.chats.empty": (
        "مفيش محادثات لسه. أول ما حد يبعت لحساب Telegram Business بتاعك (والبوت مربوط "
        "من تيليجرام ← Business ← Chatbots) أو يكتب للبوت على الخاص، هيظهر هنا."
    ),
    "tool.chats.title": "🗂 <b>آخر المحادثات</b>\nاضغط على أي واحدة تشوف آخر الرسائل.",
    "tool.chats.label": "{name} · {count} رسالة",
    "tool.transcript.title": "💬 <b>{name}</b> · المحادثة <code>{chat_id}</code>",
    "tool.transcript.empty": (
        "\n<i>مفيش رسائل محفوظة (السجل بيبدأ من وقت تشغيل البوت).</i>"
    ),
    "tool.transcript.customer": "👤 العميل",
    "tool.transcript.bot": "🤖 البوت",
    "tool.transcript.pause_state": "الرد التلقائي على المحادثة دي: <b>{state}</b>",
    "tool.transcript.paused": "موقوف ⏸",
    "tool.transcript.active": "شغّال ▶️",
    "tool.transcript.reply_hint": "للرد بنفسك: <code>/reply {chat_id} النص بتاعك</code>",
    "tool.chat.usage": "الاستخدام: /chat <chat_id> …",
    "tool.chat.none": "مفيش رسائل عندي لهذا الرقم لسه.",
    "tool.reply.usage": (
        "الاستخدام: <code>/reply &lt;chat_id&gt; الرسالة</code>\n"
        "ابعت رقم المحادثة بس وأنا هطلب منك النص.\n"
        "ملاحظة: رقم المحادثة بيظهر في كل إشعار وفي /chats."
    ),
    "tool.reply.ask": (
        "✍️ ابعت الرسالة اللي عايزني أوصلها للمحادثة <code>{chat_id}</code>.\n"
        "<i>(أو /cancel للإلغاء)</i>"
    ),
    "tool.reply.unknown_chat": "رقم محادثة غير معروف.",
    "tool.reply.cannot_reply": "حساب Telegram Business مش قادر يرد دلوقتي.",
    "tool.reply.failed": "معرفتش أبعت ({error}). راجع المحادثة.",
    "tool.reply.sent": (
        "✅ تم الإرسال.\nالرد التلقائي على المحادثة دي متوقف لمدة {minutes} دقيقة."
    ),
    "tool.reply.cancelled": "تم إلغاء الرد — ما اتبعتش حاجة.",
    "tool.pause.usage": "الاستخدام: /{command} <chat_id>",
    "tool.pause.done": (
        "⏸ البوت مش هيردّ على المحادثة <code>{chat_id}</code> لحد ما تعمل /handback."
    ),
    "tool.pause.resumed": "▶️ البوت رجع يردّ على المحادثة دي.",
    "tool.pause.not_paused": "المحادثة دي ما كانتش موقوفة.",

    "tool.stats.title": "📈 <b>إحصائيات</b>",
    "tool.stats.customers": "العملاء: <b>{count}</b>",
    "tool.stats.messages": (
        "الرسائل الواردة · ٢٤ ساعة: <b>{day}</b> · ٧ أيام: <b>{week}</b> · "
        "الإجمالي: <b>{total}</b>"
    ),
    "tool.stats.replies": (
        "ردود الذكاء الاصطناعي · ٢٤ ساعة: <b>{day}</b> · ٧ أيام: <b>{week}</b> · "
        "الإجمالي: <b>{total}</b>"
    ),
    "tool.stats.summary": "الوضع: <b>{mode}</b> · موافقات معلّقة: <b>{pending}</b>",
    "tool.stats.paused": "محادثات موقوفة: <b>{count}</b>",
    "tool.stats.kb": "قاعدة المعرفة: <b>{count}</b> عنصر",
    "tool.stats.faq": "الردود الجاهزة: <b>{count}</b>",
    "tool.stats.connections": "حسابات Telegram Business: <b>{count}</b>",
    "tool.stats.direct": "الرسائل الخاصة: <b>{state}</b>",

    "tool.health.title": "❤️ <b>فحص النظام</b>",
    "tool.health.telegram_ok": "✅ تيليجرام شغال — @{username}",
    "tool.health.telegram_error": "❌ خطأ في الاتصال بتيليجرام: {error}",
    "tool.health.ai_ok": "✅ الذكاء الاصطناعي جاهز — {backend} · <code>{model}</code>",
    "tool.health.ai_missing": (
        "❌ الذكاء الاصطناعي مش مُعدّ — افتح /ai لإضافة مفتاح أو اختيار مزوّد."
    ),
    "tool.health.cost": "ℹ️ التكلفة: {cost}",
    "tool.health.embeddings": "ℹ️ التمثيلات (Embeddings): {state}",
    "tool.health.embeddings_yes": "متاحة",
    "tool.health.embeddings_no": "مش متاحة (بحث بالكلمات المفتاحية)",
    "tool.health.freeai_hint": (
        "💡 المفتاح مرفوض أو مفيش رصيد؟ /freeai بيعرض المزوّدين المجانيين "
        "(Google Gemini، Groq، Cerebras، Mistral…)."
    ),
    "tool.health.no_connection": (
        "❌ مفيش حساب Telegram Business مربوط — اربط البوت من تيليجرام ← الإعدادات ← "
        "Business ← Chatbots، أو استخدم الرسائل الخاصة (/direct)."
    ),
    "tool.health.direct_ready": "✅ الرسائل الخاصة: مفعّلة — البوت بيردّ على محادثاته.",
    "tool.health.connection_row": (
        "{icon} الحساب <code>{id}…</code> · مفعّل: {enabled} · يقدر يرد: {can_reply}"
    ),
    "tool.health.enable_reply": (
        "   ↳ فعّل «Allow bot to reply to messages» للبوت من "
        "Telegram Business ← Chatbots."
    ),
    "tool.health.disk": "✅ المساحة الفاضية على القرص: {mb} ميجا",
    "tool.health.summary": "ℹ️ الوضع: <b>{mode}</b> · موافقات معلّقة: <b>{pending}</b>",
    "tool.health.aitest_hint": "ℹ️ اختبر الذكاء الاصطناعي من الأساس بـ /aitest.",
    "tool.export.caption": (
        "نسخة احتياطية: الإعدادات، الردود الجاهزة، فهرس قاعدة المعرفة "
        "(مفاتيح API ما بتتصدّرش أبدًا)"
    ),
    "tool.callback.closed": "تم الإغلاق.",
    "tool.callback.checking": "بيفحص…",
    "tool.callback.bad_chat": "رقم محادثة غلط.",
    "tool.callback.no_messages": "مفيش رسائل للمحادثة دي لسه.",
    "tool.callback.done": "تم",
    "tool.callback.paused": "⏸ تم إيقاف المحادثة <code>{chat_id}</code>.",
    "tool.callback.resumed": "▶️ تم استئناف المحادثة <code>{chat_id}</code>.",

    # =========================================================================
    # إشعارات خط الردود (محادثات Business والرسائل الخاصة)
    # =========================================================================
    "biz.welcome_default": "👋 أهلاً! نورت — أقدر أساعدك في إيه؟",
    "biz.conn.enabled": (
        "🔗 <b>تم ربط حساب Telegram Business.</b>\n"
        "رقم صاحب الحساب: <code>{owner}</code>\n"
        "البوت يقدر يرد: <b>{can_reply}</b>\n\n"
        "من دلوقتي البوت هيستقبل رسائل عملاء الحساب ده. تقدر تشوف /status في أي وقت."
    ),
    "biz.conn.no_reply_permission": (
        "⚠️ الربط ده <b>مش</b> بيدي البوت صلاحية الرد، يعني هيقرأ الرسائل ومش هيقدر "
        "يبعت. فعّل صلاحية الرد للبوت من Telegram Business ← Chatbots."
    ),
    "biz.conn.disabled": "🔌 <b>تم إيقاف أو إلغاء ربط حساب Telegram Business.</b>",
    "biz.notify.incoming": (
        "📥 <b>{name}</b> (المحادثة <code>{chat_id}</code>):\n"
        "<i>{text}</i>\n\n"
        "<i>الرد التلقائي مقفول — رد إنت بنفسك أو شغّله من /mode.</i>"
    ),
    "biz.notify.auto_replied": (
        "🤖 تم الرد تلقائيًا على <b>{name}</b>:\n"
        "<i>«{text}»</i>\n"
        "➡️ {reply}"
    ),
    "biz.notify.rate_limit": (
        "🚦 <b>{name}</b> وصل لحد الرسائل "
        "({used}/{limit} في آخر ساعة). "
        "الرد التلقائي على المحادثة دي متوقف لمدة ساعة."
    ),
    "biz.notify.ai_failed": (
        "⚠️ معرفتش أولّد رد لـ <b>{name}</b> "
        "(المحادثة <code>{chat_id}</code>): {error}"
    ),
    "biz.notify.ai_failed_tail": "ما اتبعتش أي رسالة للعميل.",
    "biz.notify.delivery_partial": (
        "⚠️ الرد التلقائي على <b>{name}</b> "
        "اتوصّل جزئيًا ({sent}/{total} أجزاء). "
        "راجع المحادثة قبل ما تبعت أي حاجة تانية."
    ),
    "biz.notify.delivery_unknown": (
        "⚠️ مش متأكد إن الرد التلقائي على <b>{name}</b> "
        "اتوصّل. مفيش سجل للرسالة الصادرة؛ راجع المحادثة قبل إعادة المحاولة."
    ),
    "biz.notify.cannot_reply": (
        "⚠️ مش قادر أرد تلقائيًا: الحساب موقوف أو مالوش صلاحية الرد. "
        "راجع Telegram Business ← Chatbots."
    ),
    "biz.notify.nontext": (
        "📎 <b>{name}</b> بعت رسالة غير نصية <i>{type}</i> "
        "(المحادثة <code>{chat_id}</code>).{suffix}"
    ),
    "biz.notify.nontext_ack": " واتبعت له رسالة التأكيد المضبوطة.",
    "biz.edited": (
        "✏️ <b>{name}</b> عدّل رسالة: "
        "<i>{text}</i>{cancellation}"
    ),
    "biz.edited_cancelled": "\nوالموافقة المعلّقة على النسخة القديمة اتلغت.",
    "biz.deleted_pending": (
        "🗑 عميل مسح رسالة كان ليها موافقة معلّقة؛ "
        "والموافقة اتلغت."
    ),

    # =========================================================================
    # main.py
    # =========================================================================
    "main.online": (
        "✅ <b>Alfiqi Ai {version} شغّال</b> على @{username}.\n"
        "الوضع: <b>{mode}</b>\n"
        "الذكاء الاصطناعي: <b>{ai_state}</b> ({backend})\n"
        "التكلفة: {cost}"
    ),
    "main.online.setup_hint": (
        "\n\nأول مرة؟ اعمل /setup للقائمة الكاملة "
        "(Business Mode في BotFather + الربط من Telegram Business ← Chatbots)."
    ),
    "main.online.direct_hint": (
        "\n\n💬 الرد على الرسائل الخاصة: {state} — أي حد يبعت للبوت رسالة خاصة "
        "بياخد رد طالما الوضع شغّال، ومن غير أي حساب Telegram Business. "
        "تقدر تتحكم فيه من /direct."
    ),
    "main.online.on": "مفعّل",
    "main.online.off": "مقفول",
    "main.online.freeai": (
        "\n\n💡 لسه مفيش مفتاح API، أو المفتاح مفيش وراه رصيد؟ ابعت /freeai "
        "للمزوّدين المجانيين — Google Gemini و Groq و Cerebras "
        "مش محتاجين بطاقة بنكية."
    ),
    "main.online.interrupted": (
        "\n\n⚠️ <b>محتاج مراجعة يدوية:</b> "
        "{count} محاولة إرسال موافقة اتقاطعت. "
        "راجع محادثة العميل قبل ما تبعت أي رد تاني."
    ),
    "main.description": (
        "Alfiqi Ai بيردّ بالذكاء الاصطناعي على الرسائل الخاصة اللي توصلك — "
        "بالعربي افتراضيًا."
    ),
    "main.description_short": "ردود ذكية على رسائلك الخاصة 🤖",
    "main.cmd.start": "لوحة التحكم",
    "main.cmd.setup": "دليل الإعداد خطوة بخطوة",
    "main.cmd.mode": "رد تلقائي / مسودة / متوقف",
    "main.cmd.ai": "مزوّد الذكاء والمفتاح والموديل",
    "main.cmd.freeai": "مزوّدين مجانيين (بدون بطاقة)",
    "main.cmd.aitest": "اختبار الاتصال بالذكاء الاصطناعي",
    "main.cmd.faq": "الردود الجاهزة (ردود فورية)",
    "main.cmd.kb": "قائمة قاعدة المعرفة",
    "main.cmd.status": "حالة البوت والذكاء والربط",
    "main.cmd.health": "فحوصات النظام",
    "main.cmd.settings": "كل الإعدادات",
    "main.cmd.chats": "آخر المحادثات",
    "main.cmd.stats": "إحصائيات",
    "main.cmd.instructions": "تعليمات دائمة (النبرة/اللغة)",
    "main.cmd.help": "دليل الاستخدام",
    "main.cmd.direct": "الرد على الرسائل الخاصة للبوت",
    "main.cmd.language": "لغة واجهة البوت (العربية/English)",

    # =========================================================================
    # /direct و /language
    # =========================================================================
    "own.direct.on": (
        "🟢 <b>الرسائل الخاصة:</b> مفعّلة — البوت بيردّ بالذكاء الاصطناعي على أي حد "
        "يبعتله رسالة خاصة، وبيجي إشعار لكل رسالة."
    ),
    "own.direct.off": (
        "🔴 <b>الرسائل الخاصة:</b> مقفولة — اللي بيكتب للبوت بياخد رسالة "
        "«المساعد مُدار» وخلاص."
    ),
    "own.direct.now": "\n\nوضع الرد: <b>{mode}</b> — البوت بيردّ فعليًا بس لما يكون "
                      "الوضع «رد تلقائي» أو «مسودة» (/mode).",
    "own.direct.hint": "\n\nتقدر تخليها {opposite} بـ <code>/direct {command}</code>.",
    "own.direct.usage": "الاستخدام: <code>/direct on|off</code> (حاليًا: {state})",
    "own.direct.on_word": "on",
    "own.direct.off_word": "off",
    "own.language.title": (
        "🌐 <b>لغة واجهة البوت</b>\n\n"
        "الحالية: <b>{label}</b>\n"
        "ده بيغيّر قوائم البوت وأزراره وإشعاراته — مش لغة الردود نفسها اللي بتتقال "
        "للعملاء (دي من /settings ← الشخصية ← لغة الرد)."
    ),

    # =========================================================================
    # handlers/settings.py
    # =========================================================================
    "set.group.reply": "🤖 الردود والسلوك",
    "set.group.persona": "🧑‍💼 الشخصية واللغة",
    "set.group.lang": "🌐 لغة البوت",
    "set.group.ai": "🧠 موديل الذكاء",
    "set.group.ground": "📚 الردود (الجاهزة / قاعدة المعرفة)",
    "set.group.limits": "🛡️ الأمان والحدود",
    "set.title": (
        "⚙️ <b>الإعدادات</b>\n"
        "وضع الرد: <b>{mode}</b> (يتغير من /mode) · "
        "الذكاء: <b>{backend}</b>\n"
        "اختر قسم:"
    ),
    "set.title_plain": "⚙️ الإعدادات",
    "set.section_hint": "{title}\nاضغط على أي سطر لتعديله.",
    "set.value.on": "مفعّل",
    "set.value.off": "مقفول",
    "set.provider_row": "🧠 المزوّد: {label}",
    "set.connection_row": "🧠 اتصال الذكاء: {label}",
    "set.model_row": "🧠 الموديل: {model}",
    "set.free_ai_row": "🆓 مزوّدين مجانيين (بدون بطاقة)",
    "set.primary_only": "المشرف الأساسي بس هو اللي يغيّر مزوّد أو موديل الذكاء.",
    "set.error": "حصل خطأ.",
    "set.closed": "تم الإغلاق.",
    "set.waiting": "مستني القيمة…",
    "set.enum_title": "اختر <b>{label}</b>:",
    "set.saved_value": "{label} → {value}",
    "set.toggle_alert": "{label} {state}",
    "set.prompt_value": "ابعت القيمة الجديدة لـ <b>{label}</b>{range}.{hint}\n\nأو /cancel للإلغاء.",
    "set.prompt_range": " (المسموح {min}–{max})",
    "set.empty": "مفيش قيمة — ما اتغيّرش حاجة.",
    "set.text_saved": "✅ تم تحديث {label}:\n<b>{value}</b>",
    "set.not_number": "«{raw}» مش رقم صحيح. {label} زي ما هو.",
    "set.out_of_range": "القيمة لازم تكون بين {low} و {high}. {label} زي ما هو.",
    "set.number_saved": "✅ تم ضبط {label} على <b>{value}</b>.",

    "set.opt.auto_reply_enabled": "الرد التلقائي",
    "set.opt.approval_mode_enabled": "الموافقة قبل الإرسال (مسودة)",
    "set.opt.sensitive_requires_approval": "الرسائل الحساسة → موافقة",
    "set.opt.monitoring_mode": "إشعاري بكل نشاط",
    "set.opt.memory_enabled": "ذاكرة المحادثات",
    "set.opt.typing_indicator": "مؤشر «بيكتب…»",
    "set.opt.reply_debounce_seconds": "تجميع الرسائل (ثواني)",
    "set.opt.process_nontext_enabled": "قراءة تعليقات الوسائط",
    "set.opt.nontext_ack_message": "رد تلقائي على الوسائط",
    "set.opt.nontext_ack_message.hint": (
        "بتتبعت لما حد يبعت صورة أو فويس من غير نص. "
        "فاضية = مفيش رد تلقائي."
    ),
    "set.opt.greet_new_customers": "ترحيب بالعملاء الجدد",
    "set.opt.welcome_text": "نص رسالة الترحيب",
    "set.opt.owner_takeover_pause_minutes": "مدة الإيقاف بعد تدخلك (دقيقة)",
    "set.opt.max_messages_per_customer_per_hour": "حد الرسائل في الساعة",
    "set.opt.direct_reply_enabled": "الرسائل الخاصة (شات البوت)",
    "set.opt.direct_reply_enabled.hint": (
        "الرد على الرسائل الخاصة اللي توصلك على شات البوت نفسه "
        "(من غير أي حساب Telegram Business). وضع الرد لسه بيتطبّق."
    ),
    "set.opt.public_direct_bot_chat_enabled": "إشعار الرسائل الخاصة",
    "set.opt.assistant_name": "اسم المساعد",
    "set.opt.assistant_name.hint": "الاسم اللي المساعد بيشير بيه لنفسه، مثال: «سارة».",
    "set.opt.business_name": "اسم صاحب الحساب",
    "set.opt.business_description": "نبذة شخصية عن صاحب الحساب",
    "set.opt.business_description.hint": "سطر أو سطرين يستخدمهم الذكاء كسياق.",
    "set.opt.tone": "النبرة",
    "set.opt.reply_language": "لغة الرد",
    "set.opt.signature": "التوقيع",
    "set.opt.signature.hint": "بيتضاف في آخر كل رد. فاضي = مفيش توقيع.",
    "set.opt.max_reply_chars": "أقصى طول للرد",
    "set.opt.disclose_ai": "يقدر يقول إنه ذكاء اصطناعي",
    "set.opt.custom_instructions": "تعليمات إضافية",
    "set.opt.custom_instructions.hint": "بتتضاف دايمًا لتعليمات الذكاء (كمان من /instructions).",
    "set.opt.reply_priorities": "أولويات الرد",
    "set.opt.reply_priorities.hint": "أولويات الرد بالترتيب، كل واحدة في سطر.",
    "set.opt.never_reply_rules": "حالات ما يردش فيها",
    "set.opt.never_reply_rules.hint": (
        "مواضيع أو حالات نتجنبها؛ المساعد هيقول إن حد من الفريق هيتواصل."
    ),
    "set.opt.ui_language": "لغة البوت",
    "set.opt.ui_language.hint": "لغة قوائم البوت وإشعاراته (العربي افتراضيًا).",
    "set.opt.temperature": "درجة الإبداع (Temperature)",
    "set.opt.max_tokens": "أقصى عدد توكنات",
    "set.opt.ai_base_url": "Base URL مخصص",
    "set.opt.faq_enabled": "الردود الجاهزة",
    "set.opt.faq_direct_reply": "المطابقة الحرفية تنزل زي ما هي",
    "set.opt.faq_match_threshold": "دقة مطابقة الردود (%)",
    "set.opt.faq_match_threshold.hint": (
        "أي كلمة مفتاحية مطابقة = 100%. اختلاف صيغة الكلمة (يوصّل ↔ توصيل) "
        "بيتحسب 50%، فبيتنزل الرد الحرفي لو قلّلت الرقم ده."
    ),
    "set.opt.kb_enabled": "قاعدة المعرفة",
    "set.opt.strict_kb_mode": "وضع قاعدة المعرفة الصارم",

    "set.tone.friendly": "ودود",
    "set.tone.professional": "رسمي ومهني",
    "set.tone.casual": "عفوي وبسيط",
    "set.tone.concise": "مختصر جدًا",
    "set.tone.warm": "دافئ ومتعاطف",
    "set.lang.auto": "تلقائي (حسب لغة العميل)",
    "set.lang.ar": "العربية",
    "set.lang.en": "English",
    "set.lang.fr": "Français",
    "set.lang.es": "Español",
    "set.lang.de": "Deutsch",
    "set.lang.tr": "Türkçe",
    "set.lang.fa": "فارسی",
    "set.lang.ur": "اردو",
    "set.lang.ru": "Русский",
    "set.lang.id": "Bahasa Indonesia",
    "set.lang.hi": "हिन्दी",
    "set.lang.zh": "中文",

    # =========================================================================
    # handlers/setup_guide.py (/setup)
    # =========================================================================
    "setup.title": "🚀 <b>الإعداد</b>",
    "setup.tap_hint": "اضغط على أي خطوة تحت تطلعلك التعليمات بالتفصيل.",
    "setup.connection.live": "حساب Telegram Business: <b>مربوط ويقدر يرد</b> ✅",
    "setup.connection.readonly": (
        "فيه حساب Telegram Business مربوط، بس البوت <b>مش مسموح له يرد</b> — "
        "فعّل الصلاحية من Telegram Business ← Chatbots ⚠️"
    ),
    "setup.connection.none": (
        "لسه مفيش حساب Telegram Business مربوط — ده الخطوة 2️⃣ فوق. "
        "ومش مستخدم Telegram Business؟ متعملهاش: /direct بيخلي البوت يردّ على "
        "الرسائل الخاصة اللي توصله هو نفسه."
    ),
    "setup.direct": "الرسائل الخاصة: <b>مفعّلة</b> — من غير أي حساب Telegram Business ✅",
    "setup.extra.current": "الحالي: {value}",
    "setup.extra.content": "عناصر قاعدة المعرفة: {items} · الردود الجاهزة: {faq}",
    "setup.extra.connections": "الحسابات المربوطة: {count}",
    "setup.step.secretary.label": "1️⃣ تفعيل Business/Secretary Mode في @BotFather",
    "setup.step.business.label": "2️⃣ الربط من Telegram Business ← Chatbots",
    "setup.step.ai.label": "3️⃣ اختيار مزوّد الذكاء الاصطناعي",
    "setup.step.content.label": "4️⃣ إضافة ردودك (ردود جاهزة / قاعدة معرفة)",
    "setup.step.mode.label": "5️⃣ اختيار وضع الرد",
    "setup.step.test.label": "6️⃣ ابعت رسالة تجريبية",
    "setup.step.secretary.body": (
        "1️⃣ <b>فعّل وضع Business (Secretary)</b>\n\n"
        "تيليجرام مش بيسمح للبوت يرد نيابة عنك غير لما يكون مفعّل عليه وضع "
        "Business:\n\n"
        "١. افتح <b>@BotFather</b> في تيليجرام\n"
        "٢. ابعت /mybots\n"
        "٣. اختر البوت ده\n"
        "٤. <b>Bot Settings</b> ← <b>Business Mode</b> (في نسخ بتسمى "
        "<b>Secretary Mode</b>)\n"
        "٥. اضغط <b>Turn on</b>\n\n"
        "وبعدين ارجع وشوف القائمة دي تاني بـ /setup.\n"
        "<i>الخطوة دي مطلوبة بس للرد على محادثات حساب Telegram Business — "
        "الرسائل الخاصة للبوت شغالة من غيرها.</i>"
    ),
    "setup.step.business.body": (
        "2️⃣ <b>اربط البوت بحساب Telegram Business</b>\n\n"
        "محتاج <b>Telegram Premium</b> على الحساب اللي هيرد على العملاء.\n\n"
        "١. تيليجرام ← <b>الإعدادات</b>\n"
        "٢. افتح <b>Telegram Business</b>\n"
        "٣. افتح <b>Chatbots</b>\n"
        "٤. الصق يوزر البوت ده\n"
        "٥. اختر هو يرد على مين: <b>كل المحادثات الخاصة ما عدا…</b> "
        "(الأفضل) أو محادثات معينة\n"
        "٦. من <b>Bot permissions</b> فعّل "
        "<b>«Allow bot to reply to messages»</b> — من غيرها البوت هيقرأ ومش هيرد\n"
        "٧. احفظ\n\n"
        "أول ما الربط يشتغل هيجيلك إشعار هنا، و/status بيوضّح إذا كان يقدر يرد ولا لأ."
    ),
    "setup.step.ai.body": (
        "3️⃣ <b>اختر مزوّد الذكاء الاصطناعي</b>\n\n"
        "افتح /ai واختر واحد — من غير أي أوامر في الطرفية. <b>مفيش بطاقة بنكية؟</b> "
        "ابعت /freeai للقائمة الكاملة، والملخص:\n\n"
        "• <b>Google Gemini</b> 🆓 — أسخى طبقة مجانية، يكفي حساب جوجل\n"
        "• <b>Groq</b> 🆓 / <b>Cerebras</b> 🆓 — سريعين جدًا ومجانيين بإيميل\n"
        "• <b>OpenRouter</b> 🆓 — مفتاح واحد لموديلات كتير (استخدم اسم بينتهي بـ "
        "<code>:free</code>)\n"
        "• <b>Mistral</b> و <b>NVIDIA</b> و <b>SambaNova</b> و <b>Hugging Face</b> 🆓 — "
        "طبقات مجانية إضافية\n"
        "• <b>Pollinations</b> 🆓 — من غير مفتاح خالص (بطيء وعلى أقصى تقدير)\n"
        "• <b>Ollama / LM Studio</b> 💻 — مجاني وخاص، بيشتغل على جهازك\n"
        "• <b>OpenAI</b> و <b>Anthropic</b> و <b>DeepSeek</b> 💳 — مدفوع: الحساب "
        "لازم يكون فيه رصيد، واشتراك ChatGPT/Claude مش كفاية\n\n"
        "بعد كده اضغط «🧪 اختبار الاتصال» — المفروض تشوف الموديل بيرد. ولو فشل، "
        "البوت هيقولك السبب بالظبط (مفتاح غلط · مفيش رصيد · اسم موديل غلط) "
        "ويعرض عليك مزوّد مجاني بضغطة واحدة."
    ),
    "setup.step.content.body": (
        "4️⃣ <b>علّم البوت ردودك</b>\n\n"
        "<b>الردود الجاهزة</b> (ابدأ بيها): ردود حرفية للأسئلة المتكررة — "
        "الأسعار، التوصيل، مواعيد العمل.\n"
        "ضيف واحد: <code>/faq_add سعر, كام, price :: أسعارنا تبدأ من 500</code>\n"
        "القائمة: /faq\n\n"
        "<b>قاعدة المعرفة</b>: محتوى أطول (سياسات، كتالوجات) بصيغة "
        "<code>.txt</code> أو <code>.md</code> أو <code>.pdf</code> أو "
        "<code>.docx</code> — ارفعها بـ /kb_upload، والقائمة /kb.\n\n"
        "القاعدة: المعلومة اللي لازم تطلع مظبوطة 100% ← رد جاهز؛ "
        "الخلفية والمعلومات العامة ← قاعدة المعرفة."
    ),
    "setup.step.mode.body": (
        "5️⃣ <b>اختر طريقة الإرسال</b>\n\n"
        "• 📝 <b>وضع المسودة</b> (الأأمن): البوت بيكتب الرد ويستنى — إنت تضغط "
        "إرسال / تعديل / رفض.\n"
        "• 🟢 <b>رد تلقائي</b>: البوت يرد في الحال، وبيجيلك إشعار بكل رد.\n"
        "• 🔴 <b>متوقف</b>: البوت بس بيبلّغك.\n\n"
        "استخدم /mode في أي وقت. ابدأ بوضع المسودة يوم أو اتنين، وبعدين حوّل "
        "للرد التلقائي لما تطمّن على الردود."
    ),
    "setup.step.test.body": (
        "6️⃣ <b>اختبر من الأول للآخر</b>\n\n"
        "١. من حساب تيليجرام <b>تاني</b> (موبايل صاحبك مثلاً) ابعت رسالة لحساب "
        "Telegram Business بتاعك — أو ابعت للبوت ده على الخاص مباشرة.\n"
        "٢. وفي وضع المسودة، هيجيلك كارت موافقة هنا — اضغط إرسال.\n"
        "٣. وفي وضع الرد التلقائي، الرد بينزل لوحده.\n\n"
        "مفيش حاجة بتوصلك؟ اعمل /health، وتأكد إن «Allow bot to reply to messages» "
        "مفعّلة في Telegram Business ← Chatbots."
    ),

    # =========================================================================
    # handlers/approvals.py
    # =========================================================================
    "appr.sensitive_banner": "🚨 <b>رسالة حساسة</b> — راجعها بتركيز\n\n",
    "appr.card": (
        "{banner}📨 <b>موافقة #{id}</b>\n"
        "من: <b>{name}</b> (المحادثة <code>{chat_id}</code>)\n\n"
        "<b>الرسالة الواردة:</b>\n<i>{customer}</i>\n\n"
        "<b>الرد المقترح:</b>\n{reply}"
    ),
    "appr.something_wrong": "حصلت مشكلة.",
    "appr.bad_action": "أمر غير صحيح.",
    "appr.not_found": "الموافقة دي مش موجودة.",
    "appr.sending": "الإرسال شغال بالفعل.",
    "appr.uncertain": "مش متأكدين الإرسال تم ولا لأ. راجع محادثة العميل قبل ما تبعت تاني.",
    "appr.already": "اتعمل بالفعل: {status}.",
    "appr.unknown_action": "أمر غير معروف.",
    "appr.conn_unavailable": "الحساب مش متاح أو مش قادر يرد.",
    "appr.send_failed": "الإرسال فشل؛ الموافقة لسه معلّقة. جرّب تاني.",
    "appr.partial": "جزء من الرد اتوصّل. راجع محادثة العميل قبل ما تبعت تاني.",
    "appr.state_failed": "الرد اتوصّل، بس حالة الموافقة ما اتحفظتش.",
    "appr.sent": "اتبعت ✅",
    "appr.already_handled": "اتعمل بالفعل.",
    "appr.rejected": "اترفض 🚫",
    "appr.paused": "تم إيقاف المحادثة ⏸ (للرجوع استخدم /resume_chat).",
    "appr.edit_prompt_cb": "ابعتلي نص الرد المعدّل.",
    "appr.edit_prompt": (
        "✏️ <b>بتعدّل الرد بتاع الموافقة #{id}</b> "
        "(المحادثة <code>{chat_id}</code>).\n"
        "ابعت نص الرد الجديد في رسالتك الجاية، أو /cancel للإلغاء."
    ),
    "appr.edit.not_pending": "الموافقة دي مابقتش معلّقة.",
    "appr.edit.empty": "التعديل فاضي فاتجاهل؛ الموافقة لسه معلّقة.",
    "appr.edit.conn": "الحساب مش متاح؛ الرد المعدّل ما اتبعتش.",
    "appr.edit.handled": "الموافقة دي اتعملت بالفعل.",
    "appr.edit.failed": "الرد المعدّل ما اتوصلش. الموافقة لسه معلّقة؛ جرّب تاني.",
    "appr.edit.partial": "جزء من الرد المعدّل اتوصّل. راجع محادثة العميل قبل ما تبعت تاني.",
    "appr.edit.state_failed": "الرد المعدّل اتوصّل، بس حالة الموافقة ما اتحفظتش.",
    "appr.edit.sent": "الرد المعدّل اتبعت ✅",
    "appr.pending.none": "مفيش موافقات معلّقة. 🎉",
    "appr.pending.title": "<b>موافقات معلّقة ({count}):</b>",
    "appr.pending.row": "• #{id} المحادثة <code>{chat_id}</code>: <i>{preview}</i>",
    "appr.pending.hint": "\nكل موافقة اتبعتت في رسالة لوحدها بأزرار التصرف.",

    # =========================================================================
    # handlers/faq.py — الردود الجاهزة
    # =========================================================================
    "faq.menu.title": "💬 <b>الردود الجاهزة</b>",
    "faq.menu.entries": "عدد الردود: <b>{total}</b> ({active} مفعّل)",
    "faq.menu.direct": "المطابقة الحرفية ← يتقال زي ما هو: <b>{state}</b>",
    "faq.menu.fuzzy": "التشابه الجزئي ← يتضاف للذكاء كسياق: <b>{state}</b>",
    "faq.menu.example": (
        "مثال: كلمات مفتاحية <code>سعر, كام, price</code> ← الرد "
        "«الأسعار تبدأ من 500 جنيه» بيتقال فورًا لما أي حد يسأل عن السعر."
    ),
    "faq.menu.add": "للإضافة: <code>/faq_add كلمة1, كلمة2 {sep} الرد الحرفي</code>",
    "faq.add.step1": (
        "➕ <b>رد جاهز جديد — خطوة 1/2</b>\n\n"
        "ابعت الكلمات المفتاحية مفصولة بفواصل.\n"
        "مثال: <code>سعر, كام, price, بكام</code>\n\n"
        "أي رسالة فيها واحدة منهم ممكن تفعّل الرد. /cancel للإلغاء."
    ),
    "faq.delete.usage": "الاستخدام: /faq_del <id>",
    "faq.delete.done": "تم حذف الرد الجاهز #{id}.",
    "faq.delete.missing": "مفيش رد رقم #{id}.",
    "faq.search.ask": "ابعت رسالة شبه اللي بيبعتها العميل للتجربة، أو /cancel.",
    "faq.search.none": (
        "مفيش رد جاهز مطابق لـ «{query}».\n"
        "رسالة زي دي الذكاء الاصطناعي هو اللي هيرد عليها."
    ),
    "faq.search.title": "🔍 نتائج البحث عن «{query}»:",
    "faq.search.mode_instant": "رد فوري ✅",
    "faq.search.mode_exact": "سياق للذكاء (كل الكلمات المفتاحية موجودة)",
    "faq.search.mode_fuzzy": "سياق للذكاء (تشابه {score})",
    "faq.list.title": "💬 <b>الردود الجاهزة</b> ({count}) — اضغط 🗑 للحذف:",
    "faq.list.empty": "لسه مفيش ردود جاهزة. ضيف واحد بـ /faq_add.",
    "faq.list.none": "مفيش ردود لسه.",
    "faq.list.next_page": "<i>الصفحة الجاية →</i>",
    "faq.clear.ask": "أمسح <b>كل</b> الردود الجاهزة؟",
    "faq.import.ask": (
        "📥 ابعت ملف JSON اللي اصدّرته قبل كده (أو /cancel).\n"
        "<i>ده هيستبدل كل الردود الجاهزة الحالية.</i>"
    ),
    "faq.import.not_json": "ده مش ملف JSON — ما اتعملش استيراد.",
    "faq.import.unreadable": "معرفتش أقرأ الملف ده كـ JSON.",
    "faq.import.bad_structure": "تركيب الملف غير متوقع.",
    "faq.import.done": "✅ تم استيراد {count} رد جاهز (والردود القديمة اتبدلت).",
    "faq.create.short_trigger": "الكلمة المفتاحية قصيرة أوي — لازم حرفين على الأقل.",
    "faq.create.empty_answer": "الرد ما ينفعش يكون فاضي.",
    "faq.create.saved": (
        "✅ تم حفظ الرد الجاهز #{id}.\n\n"
        "الكلمات المفتاحية: <code>{triggers}</code>\n"
        "الرد: {answer}\n\n"
        "<i>الرسائل المطابقة حرفيًا بتاخد الرد ده في الحال؛ والمتشابهة بتتضاف "
        "للذكاء الاصطناعي كسياق معتمد.</i>"
    ),
    "faq.cb.send_triggers": "ابعت الكلمات المفتاحية.",
    "faq.cb.step1": "➕ <b>خطوة 1/2</b> — ابعت الكلمات المفتاحية (مفصولة بفواصل)، أو /cancel.",
    "faq.cb.deleted": "تم الحذف ✅",
    "faq.cb.not_found": "الرد مش موجود.",
    "faq.cb.send_test": "ابعت رسالة للتجربة.",
    "faq.cb.preparing": "بجهّز الملف…",
    "faq.export.empty": "لسه مفيش حاجة تتصدّر.",
    "faq.export.caption": "تصدير الردود الجاهزة ({count} رد)",
    "faq.pending.short_triggers": "الكلمات دي قصيرة أوي — ما اتحفظش حاجة. جرّب /faq_add تاني.",
    "faq.pending.step2": (
        "➕ <b>خطوة 2/2</b> — ابعت الرد الحرفي للكلمات دي:\n"
        "<code>{triggers}</code>\n\n(/cancel للإلغاء)"
    ),
    "faq.pending.empty_answer": "الرد فاضي — ما اتحفظش حاجة.",

    # =========================================================================
    # handlers/knowledge_base.py
    # =========================================================================
    "kb.menu.title": (
        "📚 <b>قاعدة المعرفة</b>\n"
        "العناصر: <b>{items}</b> · الأجزاء: <b>{chunks}</b>\n"
        "الاستخدام في الردود: <b>{usage}</b> · "
        "الوضع الصارم: <b>{strict}</b>"
    ),
    "kb.add.ask": "ابعت النص اللي عايز تضيفه لقاعدة المعرفة، أو /cancel.",
    "kb.upload.ask": (
        "ابعت ملف لإضافته لقاعدة المعرفة "
        "(.txt أو .md أو .pdf أو .docx)، أو /cancel."
    ),
    "kb.upload.ask_docs": "ابعت ملف .txt/.md/.pdf/.docx، أو /cancel.",
    "kb.upload.need_document": "ابعت <b>ملف</b> (.txt/.md/.pdf/.docx).",
    "kb.upload.download_failed": "معرفتش أنزّل الملف من تيليجرام. جرّب تاني.",
    "kb.upload.done": "✅ تمت إضافة <b>{name}</b> كعنصر #{id} — {count} جزء{note}.",
    "kb.add.done": "✅ تمت إضافة عنصر #{id} — {count} جزء{note}.",
    "kb.add.note_no_embeddings": " (اتخزن للبحث بالكلمات المفتاحية؛ التمثيلات مش متاحة)",
    "kb.search.ask": "ابعت كلمة البحث، أو /cancel.",
    "kb.search.none": "مفيش نتائج مناسبة في قاعدة المعرفة.",
    "kb.search.title": "🔍 أفضل {count} نتيجة لـ <i>{query}</i>:",
    "kb.list.title": "📃 <b>عناصر قاعدة المعرفة</b> (اضغط للحذف):",
    "kb.list.empty": "قاعدة المعرفة فاضية. استخدم /kb_add أو /kb_upload.",
    "kb.delete.usage": "الاستخدام: /kb_delete <item_id>",
    "kb.delete.done": "تم حذف العنصر #{id}.",
    "kb.delete.missing": "مفيش عنصر #{id}.",
    "kb.clear.empty": "قاعدة المعرفة فاضية أصلاً.",
    "kb.clear.ask": "أمسح <b>كل {items}</b> عنصر و{chunks} جزء من قاعدة المعرفة؟",
    "kb.clear.ask_plain": "أمسح قاعدة المعرفة بالكامل؟",
    "kb.cb.send_text": "ابعت النص…",
    "kb.cb.send_file": "ابعت ملف…",
    "kb.cb.send_query": "ابعت كلمة البحث…",
    "kb.cb.deleted": "تم حذف #{id}",
    "kb.cb.now_empty": "قاعدة المعرفة بقت فاضية.",
    "kb.pending.empty": "مفيش حاجة تتضاف (رسالة فاضية).",
    "kb.pending.empty_query": "كلمة البحث فاضية.",

    # =========================================================================
    # handlers/ai_setup.py
    # =========================================================================
    "ai.title": "🤖 <b>مزوّد الذكاء الاصطناعي</b>",
    "ai.status": "الحالة: <b>{state}</b>",
    "ai.send_key_hint": "ابعت مفتاح API من الزر اللي تحت.",
    "ai.send_key_hint_or_pick": "ابعت مفتاح API من الزر اللي تحت، أو اختر مزوّد تاني.",
    "ai.primary_only_note": "\nالمشرف الأساسي بس هو اللي يغيّر مزوّد أو موديل الذكاء.",
    "ai.legend": (
        "المزوّدين اللي عليهم 🆓 عندهم طبقة مجانية تنفع؛ و 💻 بيشتغل على جهازك."
    ),
    "ai.delegate_note": (
        "المشرف الأساسي بيختار المزوّد والموديل. مفتاح المالك مشترك للردود، والبيانات الشخصية منفصلة."
    ),
    "ai.freeai_hint": (
        "💡 مفيش بطاقة بنكية أو مفيش رصيد؟ ابعت /freeai للمزوّدين المجانيين."
    ),
    "ai.get_key": "🔑 هات مفتاح من هنا: {url}",
    "ai.key_source.env": "من ملف .env (الطرفية)",
    "ai.key_source.telegram": "محفوظ من تيليجرام",
    "ai.current_key": "المفتاح الحالي: {masked} ({origin})",
    "ai.not_set": "(غير محدد)",
    "ai.base_url": "Base URL: <code>{base}</code>",
    "ai.custom_hint": "ابعت الـ Base URL واسم الموديل، ومفتاح API لو حبيت.",
    "ai.endpoint": "نقطة الوصول: <code>{base}</code>",
    "ai.local_note": "<i>لازم يكون متاح من الجهاز اللي شغّال عليه البوت.</i>",
    "ai.model_line": "الموديل: <code>{model}</code>",
    "ai.cost_line": "التكلفة: {cost}",
    "ai.needs_credit": "💡 المزوّد ده محتاج رصيد مدفوع. /freeai بيعرض المجانيين.",
    "ai.providers.free_title": (
        "🆓 <b>مزوّدين ذكاء مجانيين</b>\n\n"
        "من غير بطاقة بنكية ولا رصيد. اضغط على واحد والبوت يتحوّل له، "
        "وبعدين هيطلب منك مفتاحه (وفيه منهم مش محتاج مفتاح أصلاً)."
    ),
    "ai.providers.title": (
        "🔁 <b>اختر مزوّد الذكاء الاصطناعي</b>\n\n"
        "الموديل ده هو اللي هيرد على رسائل العملاء. تقدر تغيّره في أي وقت — "
        "مفيش حاجة تانية في البوت بتتأثر."
    ),
    "ai.free.title": "🆓 <b>مزوّدين الذكاء المجانيين بالكامل</b>",
    "ai.free.intro": "من غير بطاقة بنكية ولا رصيد. اختر واحد، هات مفتاحه، واضغط عليه هنا:",
    "ai.free.active": "  ← شغّال حاليًا",
    "ai.free.no_key_needed": "    🔑 مش محتاج مفتاح API",
    "ai.free.which": (
        "<b>تختار مين؟</b>\n"
        "• الأسهل والأسخى: <b>Google Gemini</b> (حساب جوجل يكفي).\n"
        "• الأسرع: <b>Groq</b> أو <b>Cerebras</b>.\n"
        "• موديلات كتير بمفتاح واحد: <b>OpenRouter</b> (استخدم موديل بينتهي بـ "
        "<code>:free</code>).\n"
        "• من غير تسجيل خالص: <b>Pollinations</b> — بس بطيء وعلى أقصى تقدير.\n"
        "• من غير إنترنت وخصوصية كاملة: <b>Ollama</b> أو <b>LM Studio</b> على جهازك.\n\n"
        "الطبقات المجانية عندها حدود معدل (في الدقيقة / اليوم) وبتترجع لوحدها. "
        "بعد التبديل اضغط 🧪 اختبار الاتصال — ولو اسم موديل اترفض، "
        "استخدم 🔄 تحميل الموديلات تشوف مفتاحك بيشغّل إيه."
    ),
    "ai.unknown_provider": "مزوّد غير معروف.",
    "ai.provider_set": "المزوّد: {label}",
    "ai.models.title": (
        "🧠 <b>موديل {label}</b>\n\n"
        "الحالي: <code>{current}</code>\n"
        "اختر واحد، أو اكتب أي اسم موديل حسابك بيدعمه."
    ),
    "ai.primary_only_cb": "المشرف الأساسي بس هو اللي يغيّر مزوّد أو موديل الذكاء.",
    "ai.model_set_cb": "الموديل: {model}",
    "ai.testing": "بختبر…",
    "ai.remove_key_ask": (
        "أحذف مفتاح API المحفوظ بتاع <b>{label}</b>؟\n"
        "البوت هيبطّل يولّد ردود لحد ما تضيف مفتاح تاني."
    ),
    "ai.ask_key_cb": "ابعت المفتاح في رسالتك الجاية.",
    "ai.key_url_hint": "\n\n🔑 هاته من هنا: {url}",
    "ai.key_url_free": "  (مجاني — من غير بطاقة)",
    "ai.ask_key": (
        "🔑 ابعت مفتاح API بتاع <b>{label}</b> في رسالتك الجاية "
        "(أو /cancel).\n\n<i>بمسح الرسالة في الحال بعد ما أقراها.</i>{hint}"
    ),
    "ai.switched": "اتحوّلنا لـ {label}",
    "ai.no_key_needed_test": "✅ <b>{label}</b> مش محتاج مفتاح API. بختبره دلوقتي…",
    "ai.ask_model_cb": "اكتب اسم الموديل.",
    "ai.ask_model": (
        "🧠 ابعت اسم الموديل بتاع <b>{label}</b> "
        "(مثال: <code>gpt-4.1-mini</code> أو <code>gemini-2.5-flash</code>)، أو /cancel."
    ),
    "ai.ask_base_url_cb": "ابعت الـ Base URL.",
    "ai.ask_base_url": (
        "🌐 ابعت الـ Base URL بتاع نقطة الوصول المتوافقة مع OpenAI "
        "(مثال: <code>http://localhost:1234/v1</code>)، أو /cancel."
    ),
    "ai.aimodel.usage": (
        "الموديل الحالي: <code>{model}</code>\n"
        "الاستخدام: <code>/aimodel &lt;model-name&gt;</code>"
    ),
    "ai.aimodel.set": "✅ تم ضبط الموديل على <code>{model}</code>. استخدم /aitest للتأكد.",
    "ai.pending.nothing": "ما وصلنيش حاجة — اتلغى. ✖",
    "ai.pending.model_set": (
        "✅ تم ضبط الموديل على <code>{model}</code>.\nاتأكد بـ /aitest."
    ),
    "ai.pending.base_url_set": (
        "✅ تم حفظ الـ Base URL: <code>{url}</code>.\n"
        "ابعت اسم الموديل بعدها بـ /aimodel، وبعدين /aitest."
    ),
    "ai.checking_key": "🔎 بختبر المفتاح مع {label}…",
    "ai.key_rejected": "⚠️ <b>{label}</b> رفض المفتاح ده",
    "ai.connected": (
        "✅ تم الاتصال بـ <b>{label}</b>.\n{message}\n\nالموديل: <code>{model}</code>"
    ),
    "ai.how_to_fix": "<b>إزاي تحلّها</b>",
    "ai.switch_hint": "أو حوّل لمزوّد مجاني بضغطة واحدة 👇 ({names})",
    "ai.loading_models": "بجيب الموديلات…",
    "ai.asking_models": "🔄 بسأل <b>{label}</b> عن الموديلات اللي مفتاحك يقدر يستخدمها…",
    "ai.still_type_model": "تقدر برضه تكتب اسم الموديل بنفسك: /aimodel &lt;name&gt;",
    "ai.no_model_list": (
        "{label} مارجّعش قائمة موديلات. اكتب الاسم بنفسك: /aimodel &lt;name&gt;"
    ),
    "ai.models_found": (
        "🧠 <b>{count} موديل</b> مفتاحك يقدر يشغّلهم على {label}\n"
        "الحالي: <code>{current}</code>\nاضغط على واحد لاستخدامه:"
    ),
    "ai.choose_model": "🧠 اختر موديل لـ {label} (الحالي: <code>{current}</code>):",
    "ai.testing_msg": "🧪 بختبر الاتصال (ممكن ياخد ثواني)…",
    "ai.test_failed": "⚠️ <b>الاختبار فشل</b>",


    # =========================================================================
    # services/ai_service.py — تشخيص المفاتيح والنصائح والحالة
    # =========================================================================
    "util.or_join": " أو ",
    "ai.hint.openai": "OpenAI محتاج رصيد على حساب الـ API — اشتراك ChatGPT Plus "
                      "مش رصيد API (platform.openai.com ← Billing).",
    "ai.hint.anthropic": "Anthropic محتاج رصيد على console.anthropic.com — اشتراك "
                         "Claude مش رصيد API.",
    "ai.hint.google": "استخدم مفتاح من aistudio.google.com/app/apikey (Gemini API)، "
                      "مش توكن Google Cloud OAuth.",
    "ai.hint.groq": "مفاتيح Groq من console.groq.com/keys — حساب مجاني ومن غير بطاقة.",
    "ai.hint.cerebras": "مفاتيح Cerebras من cloud.cerebras.ai ← API Keys.",
    "ai.hint.openrouter": "OpenRouter: الموديلات اللي بتنتهي بـ ':free' مش محتاجة رصيد؛ "
                          "أي موديل تاني محتاج رصيد مدفوع.",
    "ai.hint.mistral": "الخطة المجانية في Mistral محتاجة تأكيد رقم تليفون قبل ما المفتاح يشتغل.",
    "ai.hint.nvidia": "NVIDIA: انسخ اسم الموديل بالظبط زي ما build.nvidia.com بيعرضه "
                      "(مثال: meta/llama-3.1-8b-instruct).",
    "ai.hint.huggingface": "Hugging Face: استخدم توكن صلاحيته 'Read'، وافتح صفحة الموديل "
                           "مرة واحدة تقبل ترخيصه لو كان مقيّد.",
    "ai.hint.deepseek": "مفاتيح DeepSeek بتشتغل بس بعد ما تشحن الرصيد "
                        "(platform.deepseek.com ← Top up).",
    "ai.hint.together": "Together محتاج حد أدنى من الشحن قبل ما المفتاح يشتغل.",
    "ai.hint.pollinations": "Pollinations مش محتاج مفتاح أصلاً — خطأ 402/429 هنا معناه "
                            "إن الخانة المجانية لكل IP مشغولة: استنى حوالي 30 ثانية وجرّب تاني.",
    "ai.hint.free": "مزوّدين مجانيين من غير بطاقة: Google Gemini و Groq و Cerebras و "
                    "Mistral — افتح /ai ← 🆓 المزوّدين المجانيين (أو ابعت /freeai).",
    "ai.classify.generic_label": "المزوّد",
    "ai.classify.model": (
        "{label} رفض اسم الموديل{tail} ممكن مفتاحك مش مصرّح له، أو الاسم مكتوب "
        "بشكل مختلف عند المزوّد ده."
    ),
    "ai.classify.pollinations_busy": (
        "{label} بيهدّي الطلبات من العنوان ده{tail} النقطة المجانية بتسمح بطلب "
        "واحد كل 30 ثانية تقريبًا: استنى شوية وجرّب تاني."
    ),
    "ai.classify.no_credit": (
        "{label}: المفتاح اتفهم، بس الحساب مفيش فيه رصيد أو الكوتة المدفوعة خلصت{tail}"
    ),
    "ai.classify.rate_limit": (
        "{label} وصل لحد المعدل أو الكوتة{tail} الطبقات المجانية بتحسب الطلبات "
        "في الدقيقة أو اليوم — ودي بترجع لوحدها، مفيش حاجة باظت."
    ),
    "ai.classify.region": (
        "{label} رفض الطلب بسبب بلدك أو منطقتك{tail} أي مزوّد تاني هيشتغل."
    ),
    "ai.classify.verify_suffix": " خلّص توثيق الحساب الأول.",
    "ai.classify.auth": "{label} رفض مفتاح الـ API ده (HTTP {status}){tail}{extra}",
    "ai.classify.not_found": (
        "{label} رجّع 404 — يعني الـ Base URL أو مسار النقطة غلط "
        "(معظم المزوّدين بيحتاجوا الـ Base URL ينتهي بـ /v1){tail}"
    ),
    "ai.classify.too_many": (
        "{label} بيحدّ من معدل طلبات البوت حاليًا{tail} الطبقات المجانية بتحسب "
        "الطلبات في الدقيقة أو اليوم؛ وده بيرجع لوحده."
    ),
    "ai.classify.server": "{label} عنده مشكلة دلوقتي (HTTP {status}). جرّب بعد شوية.{tail}",
    "ai.classify.other": "{label} رفض الطلب (HTTP {status}).{tail}",
    "ai.hint_rule.no_credit.1": "دي مشكلة رصيد أو كوتة، مش مفتاح بايظ — إعادة إرسال نفس "
                                "المفتاح مش هتحل حاجة.",
    "ai.hint_rule.no_credit.2": "يا تشحن الرصيد من صفحة الفوترة بتاعة المزوّد، يا تتحوّل "
                                "لمزوّد عنده طبقة مجانية حقيقية.",
    "ai.hint_rule.auth.1": "اتأكد إن المفتاح متنسخ من المزوّد ده بالذات — مفتاح "
                           "Groq أو OpenRouter أو Gemini مش بيشتغل على مزوّد تاني.",
    "ai.hint_rule.auth.2": "الصقه تاني من غير مسافات أو أسطر جديدة، واتأكد إنه مش ملغي "
                           "أو منتهي.",
    "ai.hint_rule.auth.new_key": "اعمل مفتاح جديد من هنا: {url}",
    "ai.hint_rule.model.1": "افتح /ai ← 🧠 تغيير الموديل ← 🔄 تحميل الموديلات من المزوّد "
                            "تشوف الأسماء اللي مفتاحك يقدر يشغّلها بالظبط.",
    "ai.hint_rule.model.2": "الطبقات المجانية كتير منها بتسمح بموديلات معينة — اختر واحد "
                            "أصغر أو أقدم.",
    "ai.hint_rule.rate_limit.1": "استنى دقيقة وشغّل /aitest تاني؛ الكوتة المجانية بترجع "
                                 "كل دقيقة أو كل يوم.",
    "ai.hint_rule.rate_limit.2": "لو عايز كوتة يومية مجانية أكبر استخدم Google Gemini أو "
                                 "Groq أو Cerebras.",
    "ai.hint_rule.bad_request": "اتأكد إن الـ Base URL بينتهي بـ /v1 وإن اسم الموديل "
                                "مطابق للتوثيق بتاع المزوّد.",
    "ai.hint_rule.connection": "معرفناش نوصل للسيرفر — اتأكد من الإنترنت على الجهاز ده، "
                               "والـ DNS، وأي جدار ناري أو بروكسي.",
    "ai.hint_rule.timeout": "المزوّد أخد وقت طويل. جرّب تاني، أو اختار مزوّد أسرع "
                            "(Groq و Cerebras بيردّوا في أقل من ثانية).",
    "ai.hint_rule.no_key.1": "افتح /ai ← 🔑 إضافة أو تحديث مفتاح API.",
    "ai.err.timeout": "{what} أخد وقت أطول من المسموح. جرّب تاني.",
    "ai.err.network": "معرفناش نوصل للمزوّد ({error}). اتأكد من الشبكة.",
    "ai.err.no_base_url": "مفيش Base URL مضبوط للنقطة دي.",
    "ai.err.no_base_url_list": "مفيش Base URL مضبوط للنقطة دي.",
    "ai.err.no_base_url_probe": "مفيش Base URL مضبوط للنقطة دي.",
    "ai.err.no_key": "مفيش مفتاح API مضبوط للمزوّد ده. ضيف واحد من /ai.",
    "ai.err.no_anthropic_key": "مفيش مفتاح API لـ Anthropic. ضيف واحد من /ai.",
    "ai.err.empty_reply": "الموديل رجّع رد فاضي.",
    "ai.err.no_embeddings_full": "التمثيلات (embeddings) مش متاحة للمزوّد الحالي "
                                 "(قاعدة المعرفة هتستخدم البحث بالكلمات المفتاحية).",
    "ai.err.no_embeddings_url": "مفيش Base URL للتمثيلات.",
    "ai.err.embeddings_payload": "نقطة التمثيلات رجّعت بيانات غير متوقعة.",
    "ai.err.unknown_provider": "مزوّد غير معروف: {provider}",
    "ai.err.codex_missing": "الـ Codex CLI مش متثبّت على الجهاز ده.",
    "ai.err.model_list_timeout": "{label}: جلب قائمة الموديلات أخد وقت أطول من المسموح.",
    "ai.err.model_list_unreachable": "معرفناش نوصل لـ {label} ({error}).",
    "ai.err.model_list_not_json": "{label} رجّع قائمة موديلات مش بصيغة JSON.",
    "ai.err.non_json": "{what}: المزوّد رجّع رد مش بصيغة JSON.",
    "ai.err.what_failed": "{what} فشل.",
    "ai.shape.bot_token": (
        "ده توكن بوت تيليجرام بتاعك (من @BotFather)، مش مفتاح API للذكاء الاصطناعي. "
        "توكن البوت مستخدم بالفعل — اللي {label} محتاجه مفتاح API خاص بيه من "
        "موقع المزوّد نفسه."
    ),
    "ai.shape.other_provider": (
        "شكله مفتاح بتاع {names}، بس إنت بتضيفه لـ {label}. كل مزوّد بيقبل "
        "مفاتيحه هو بس."
    ),
    "ai.check.no_key": "لسه مفيش مفتاح API لـ {label}.",
    "ai.check.no_key_hint": "ابعت المفتاح: /ai ← 🔑 إضافة أو تحديث مفتاح API.",
    "ai.check.get_one_at": " هاته من هنا: {url}.",
    "ai.check.shape_hint": "إنت بتضيف مفتاح لـ {label}؛ هاته من {source}",
    "ai.check.that_console": "لوحة تحكّم المزوّد ده.",
    "ai.check.belongs_to": "المفتاح ده بتاع {label}: {url}",
    "ai.check.ok": "الاتصال تمام — {label} رد بـ «{sample}» باستخدام {model} ({seconds} ثانية).",
    "ai.status.provider": "المزوّد: {label}",
    "ai.status.model": "الموديل: {model}",
    "ai.status.codex": "Codex CLI: {cli} · تسجيل الدخول: {login}",
    "ai.status.found": "موجود",
    "ai.status.not_found": "مش موجود",
    "ai.status.yes": "أيوه",
    "ai.status.no_unknown": "لأ أو مش معروف",
    "ai.status.from_env": " (من ملف .env)",
    "ai.status.in_telegram": " (محفوظ من تيليجرام)",
    "ai.status.api_key": "مفتاح API: {masked}{origin}",
    "ai.status.api_key_optional": "مفتاح API: {masked} (اختياري هنا)",
    "ai.status.base_url": "Base URL: {url}",
    "ai.status.endpoint": "نقطة الوصول: {url}",
    "ai.status.embeddings": "التمثيلات: {state}",
    "ai.status.keyword_only": "لأ (بحث بالكلمات المفتاحية بس)",
    "ai.status.cost": "التكلفة: {cost}",
    "ai.cost.local": "مجاني — بيشتغل على جهازك 💻",
    "ai.cost.no_key": "مجاني — مش محتاج مفتاح API 🆓",
    "ai.cost.free_tier": "فيه طبقة مجانية 🆓",
    "ai.cost.beyond": " (وبعدها محتاج رصيد مدفوع)",
    "ai.cost.paid": "مدفوع — الحساب محتاج رصيد 💳",
    "ai.cost.endpoint": "بيعتمد على نقطة الوصول بتاعتك",
    "ai.model_label.codex_cli": "ChatGPT من خلال Codex CLI",
    "ai.model_label.codex_default": "الافتراضي في Codex",
    "ai.what.chat": "محادثة {label}",
    "ai.what.embeddings": "تمثيلات {label}",
    "ai.what.anthropic_test": "اختبار Anthropic",
    "ai.what.test": "اختبار {label}",
    "kbd.rule.add": "✍️ ابعت التعليمات",
    "kbd.rule.list": "📃 قائمة القواعد",
    "kbd.rule.ask_questions": "❓ أسئلة بدون إجابة",
    "kbd.rule.approve": "✅ اعتماد وتطبيق",
    "kbd.rule.edit": "✏️ عدّل النص وابعته تاني",
    "kbd.rule.discard": "🗑 إلغاء",
    "kbd.res.add": "🔗 إضافة مصدر",
    "kbd.res.list": "📃 قائمة المصادر",
    "kbd.unans.answer": "✍️ الإجابة",
    "kbd.unans.ignore": "🚫 تجاهل",
    "kbd.gate.subscription": "🔒 الاشتراك الإجباري (القنوات)",
    "kbd.gate.stars": "⭐ الرسائل المدفوعة (نجوم)",
    "kbd.gate.list": "📃 المطلوب حاليًا",
    "kbd.gate.add_channel": "➕ إضافة قناة/جروب",
    "kbd.gate.refund": "↩️ استرجاع دفع النجوم ده",
    "kbd.paid.buy": "⭐ ادفع {stars} وابعت رسالتي",
    # =========================================================================
    # handlers/gates.py — بوابات الدخول (/gate)
    # =========================================================================
    "gate.title": "🚪 <b>بوابات الدخول</b>",
    "gate.body": (
        "البوابتين مقفولين افتراضيًا وبيتطبّقوا على <b>الرسائل الخاصة</b> اللي "
        "الناس بتبعتها للبوت. محادثات Telegram Business مش بتتأثر خالص، فأي حاجة "
        "شغالة دلوقتي هتفضل شغالة."
    ),
    "gate.hint": "شغّلهم من هنا وقت ما تحب.",
    "gate.sub.title": "🔒 <b>الاشتراك الإجباري</b>",
    "gate.sub.body": (
        "لازم كل واحد يشترك في القنوات/الجروبات اللي تحت قبل ما البوت يرد. "
        "الناس بتاخد أزرار اشتراك، وبعدها زر ✅ للتحقق."
    ),
    "gate.sub.empty": "لسه مفيش قنوات.",
    "gate.sub.add_hint": "الحالة الحالية: <b>{state}</b>",
    "gate.sub.ask": (
        "ابعت رابط قناة عامة أو <code>@username</code>، أو للقنوات الخاصة "
        "<code>@username | العنوان | رابط الدعوة</code>. والبوت لازم يكون مشرف "
        "هناك علشان يقدر يتحقق من الاشتراك."
    ),
    "gate.sub.saved": "✅ تمت إضافة #{id} <b>{title}</b> (<code>{ref}</code>).",
    "gate.sub.on_alert": "الاشتراك الإجباري اتفعّل",
    "gate.sub.off_alert": "الاشتراك الإجباري اتقفل",
    "gate.sub.row_on": "مفعّلة ✅",
    "gate.sub.row_off": "متوقفة ⏸",
    "gate.sub.channel": "قناة",
    "gate.sub.group": "جروب",
    "gate.stars.title": "⭐ <b>الرسائل المدفوعة (نجوم تيليجرام)</b>",
    "gate.stars.body": (
        "كل رسالة بتكلف عدد النجوم اللي تحدده. البوت يرد على أول رسائل مجانية، "
        "وبعدها يطلب النجوم ويسلّم الرسالة أول ما تيليجرام يأكّد الدفع."
    ),
    "gate.stars.enabled": "الرسائل المدفوعة: <b>{state}</b>",
    "gate.stars.price": "سعر الرسالة: <b>{stars}</b> نجمة",
    "gate.stars.free": "رسائل مجانية قبل الدفع: <b>{count}</b>",
    "gate.stars.earned": "رسائل مدفوعة: <b>{count}</b> · النجوم المكتسبة: <b>{stars}</b>",
    "gate.stars.need_price": "⚠️ اكتب سعر أكبر من صفر — الرسائل المدفوعة هتفضل محجوبة لحد ضبط السعر.",
    "gate.stars.hint": (
        "اضغط على أي قيمة لتغييرها، أو افتح /settings ← التعلّم والمصادر لنفس "
        "المفاتيح."
    ),
    "gate.stars.on_alert": "الرسائل المدفوعة اتفعّلت",
    "gate.stars.off_alert": "الرسائل المدفوعة اتقفلت",
    "gate.price.ask": "⭐ ابعت سعر الرسالة بالنجوم كرقم (مثال: 50).",
    "gate.price.bad": "ابعت السعر أرقام بس.",
    "gate.price.range": "ابعت رقم بين 1 و {max}.",
    "gate.price.saved": "✅ السعر بقى <b>{stars}</b> نجمة، والرسائل المدفوعة اتفعّلت.",
    "gate.free.ask": "ابعت عدد الرسائل المجانية لكل شخص (0 = مفيش).",
    "gate.free.bad": "ابعت الرقم أرقام بس.",
    "gate.free.saved": "✅ الرسائل المجانية قبل الدفع: <b>{count}</b>.",
    "gate.cb.type": "ابعت القيمة في رسالتك الجاية.",
    "gate.list.title": "📃 <b>المطلوب حاليًا</b>",
    "gate.list.payments": "<b>آخر المدفوعات</b>",
    "gate.list.payment_row": "#{id} المحادثة <code>{chat_id}</code> — {stars}⭐ ({status})",
    "gate.refunded": "اتسجّل كمرتجع.",
    "gate.refund_missing": "الدفعة مش موجودة.",
    "gate.status.subscription": "الاشتراك الإجباري: <b>{state}</b> ({count} محادثة)",
    "gate.status.payments": "الرسائل المدفوعة: <b>{state}</b>",
    "gate.status.price": "السعر: <b>{stars}</b> نجمة",
    "gate.status.free": "رسائل مجانية قبل الدفع: <b>{count}</b>",
    "gate.status.earned": "المدفوع: <b>{count}</b> · النجوم: <b>{stars}</b>",
    # --- اللي بيشوفه المستخدم ---
    "gate.user.sub": (
        "🔒 قبل ما أقدر أرد عليك، لازم تشترك في القنوات/الجروبات دي:\n\n{list}\n\n"
        "بعد ما تشترك اضغط ✅ تحقّق."
    ),
    "gate.user.sub_ok": "✅ تمام، اشتراكك متأكد. ابعت رسالتك تاني 👇",
    "gate.user.still_missing": "لسه مشتركش في:\n{list}",
    "gate.user.pay": (
        "⭐ الرسالة دي بـ {stars} نجمة.\n"
        "اضغط الزرار تحت لدفع {stars} نجمة، وبعد الدفع هبعت رسالتك في الحال."
    ),
    "gate.user.free": "🎁 فاضل لك {left} رسالة مجانية.",
    "gate.pay.expired": "الفاتورة دي انتهت — ابعت رسالتك تاني.",
    "gate.pay.done": "✅ الدفع تم! بقرا رسالتك دلوقتي…",
    "gate.pay.failed": "⚠️ الدفع مكملش. جرّب تاني.",
    "gate.owner.copy": (
        "⭐ <b>رسالة مدفوعة ({stars} نجمة)</b>\n"
        "من: <b>{name}</b> (المحادثة <code>{chat_id}</code>)\n\n"
        "<b>الرسالة:</b>\n<i>{text}</i>\n\n"
        "<b>الرد:</b>\n{reply}"
    ),
    "kbd.gate.stars_toggle": "⭐ تشغيل/إيقاف الرسائل المدفوعة",
    "kbd.gate.price": "💲 تحديد السعر (نجوم)",
    "kbd.gate.free": "🎁 رسائل مجانية قبل الدفع",
    "main.cmd.rules": "التعليمات وقواعد الرد",
    "main.cmd.unanswered": "أسئلة البوت ما عرفش يرد عليها",
    "main.cmd.resources": "المصادر اللي البوت يبحث فيها",
    "main.cmd.gate": "بوابات الدخول (اشتراك / نجوم)",
    "set.group.learning": "التعلّم (القواعد والمصادر)",
    "set.group.gate": "بوابات الدخول (الرسائل الخاصة)",
    "set.opt.rules_enabled": "اتّبع قواعد الرد اللي اعتمدتها",
    "set.opt.rules_enabled.hint": (
        "تتطبّق القواعد اللي بتعتمدها من /rules على كل رد."
    ),
    "set.opt.resources_enabled": "البوت يبحث في المصادر",
    "set.opt.resources_enabled.hint": (
        "يستخدم المواقع والقنوات/الجروبات اللي ضفتها من /resources وقت ما تساعد في الرد."
    ),
    "set.opt.unanswered_enabled": "يسألك عن أي سؤال ما عرفش يرد عليه",
    "set.opt.unanswered_enabled.hint": (
        "البوت يقول إنه هيسأل الفريق، وبعدين يبعتلك السؤال من /unanswered، "
        "وإجابتك بتتحوّل لرد سريع بيتعلمه."
    ),
    "set.opt.require_subscription_enabled": "إجبار الاشتراك في قنواتي",
    "set.opt.require_subscription_enabled.hint": (
        "لازم الناس تشترك قبل ما البوت يرد، والقايمة بتتظبط من /gate. "
        "بيتطبّق على الرسائل الخاصة بس."
    ),
    "set.opt.paid_messages_enabled": "تحصيل نجوم مقابل الرسائل",
    "set.opt.paid_messages_enabled.hint": (
        "كل رسالة بتكلف السعر اللي تحت. أوقف الرسائل المدفوعة لو عايز تلغي شرط الدفع. "
        "بيتطبّق على الرسائل الخاصة بس."
    ),
    "set.opt.paid_message_stars": "سعر الرسالة (نجوم)",
    "set.opt.paid_message_stars.hint": (
        "عدد نجوم تيليجرام اللي بيدفعها الشخص قبل ما رسالته توصلك. لازم سعر أكبر من صفر عند تفعيل الرسائل المدفوعة."
    ),
    "set.opt.paid_message_free_count": "رسائل مجانية قبل الدفع",
    "set.opt.gate_copy_to_owner": "ابعتلي نسخة من الرسائل المحجوبة",
    "set.opt.gate_copy_to_owner.hint": (
        "بعد ما الرسالة المحجوبة توصل، البوت يبعتلك الرسالة والرد اللي بعته."
    ),
    "kbd.gate.verify": "✅ تأكيد اشتراكي",
    "gate.user.still_missing_alert": "لسه مشتركتش",
    "gate.invoice.title": "{name}: رسالة مدفوعة",
    "gate.invoice.default_title": "رسالة مدفوعة",
    "gate.invoice.desc": "رسالتك هتوصل لـ {name} أول ما تيليجرام يأكّد الدفع ({stars} نجمة).",
    "gate.invoice.label": "رسالة",
    "gate.user.free_last": "🎁 دي كانت آخر رسالة مجانية — من هنا ورايح كل رسالة بـ {stars} نجمة.",
    "gate.refunded_local": "الاسترجاع اتسجّل هنا، بس تيليجرام رفض استرجاع النجوم — راجع رصيد البوت.",
    # ==== append-below ====    # ==== append-below ===='''
    # =========================================================================
    # services/providers.py — registry texts (ar)
    # =========================================================================
    'prov.google.label': 'Google Gemini',
    'prov.google.docs': 'مفتاح مجاني من Google AI Studio: سجّل بحساب جوجل، اضغط «Create API key»، وخلاص. الطبقة المجانية محدودة بعدد الطلبات يوميًا (بتترجع الساعة 12 بالليل بتوقيت المحيط الهادئ)، وأحدث موديلات Pro محتاجة فوترة — أما Flash فهي المجانية. بيعمل برضه تمثيلات قاعدة المعرفة.',
    'prov.google.free_note': 'أفضل طبقة مجانية: مئات الطلبات المجانية في اليوم بأي حساب جوجل — من غير بطاقة ولا رقم تليفون.',
    'prov.groq.label': 'Groq (الأسرع)',
    'prov.groq.docs': 'مفتاح مجاني من console.groq.com — سجّل بإيميل (من غير بطاقة)، وافتح «API Keys» واعمل مفتاح. سريع جدًا. قاعدة المعرفة بتستخدم البحث بالكلمات المفتاحية (Groq مفيش عنده API للتمثيلات). وقائمة الموديلات المجانية عند Groq بتتغير كتير؛ لو اسم موديل اترفض استخدم «تحميل الموديلات».',
    'prov.groq.free_note': 'مجاني للأبد بإيميل بس: حوالي 1000 طلب يوميًا على موديلات المحادثة، وحوالي 30 طلب في الدقيقة، وردود في أجزاء من الثانية. (موديل Llama 3.3 70B اتشال من الطبقة المجانية يوم 2026-08-16، والبديل هو GPT-OSS و Qwen.)',
    'prov.cerebras.label': 'Cerebras (سريع وكوتة يومية كبيرة)',
    'prov.cerebras.docs': 'مفتاح مجاني من cloud.cerebras.ai ← API Keys (إيميل أو GitHub، من غير بطاقة). القائمة المجانية بتتغير كتير، فبعد الاتصال اضغط «تحميل الموديلات» واختر واحد مفتاحك يقدر يشغّله فعلاً. حجم السياق في الطبقة المجانية محدود (حوالي 8 آلاف توكن).',
    'prov.cerebras.free_note': 'حوالي مليون توكن مجاني يوميًا وآلاف الطلبات المجانية يوميًا — تسجيل بالإيميل أو GitHub من غير بطاقة.',
    'prov.openrouter.label': 'OpenRouter (مئات الموديلات)',
    'prov.openrouter.docs': 'مفتاح مجاني من openrouter.ai/keys. اختر موديل اسمه بينتهي بـ «:free» تفضل بتكلفة صفر — اضغط «تحميل الموديلات» وهتلاقي المجانيين في الأول. الموديلات المدفوعة محتاجة رصيد، فخطأ «مفيش رصيد» هنا معناه إنك اخترت موديل مش :free.',
    'prov.openrouter.free_note': 'مفتاح مجاني واحد لمئات الموديلات. الموديلات اللي اسمها بينتهي بـ «:free» مش بتكلف حاجة (حوالي 50 طلب مجاني يوميًا).',
    'prov.mistral.label': 'Mistral AI',
    'prov.mistral.docs': 'مفتاح مجاني من console.mistral.ai (من غير بطاقة؛ والخطة المجانية بتطلب تأكيد رقم التليفون وممكن تستخدم رسايلك لتحسين موديلاتهم لو ما أوقفتش ده). جودة كويسة في تعدد اللغات، وحوالي طلب واحد في الثانية.',
    'prov.mistral.free_note': 'خطة «Experiment» المجانية: حوالي طلب واحد في الثانية وحصة توكنز شهرية كبيرة. من غير بطاقة، بس بتطلب تأكيد رقم التليفون.',
    'prov.nvidia.label': 'NVIDIA NIM (أرصدة مجانية عند التسجيل)',
    'prov.nvidia.docs': 'مفتاح مجاني من build.nvidia.com (حساب NVIDIA، من غير بطاقة). انسخ اسم الموديل بالظبط زي ما هو مكتوب في صفحة الموديل — أسماء NVIDIA بتشمل اسم الشركة، مثال: meta/llama-3.1-8b-instruct.',
    'prov.nvidia.free_note': 'أرصدة API مجانية بحساب NVIDIA (من غير بطاقة). الأرصدة بتخلص ومابتتجددش يوميًا.',
    'prov.sambanova.label': 'SambaNova',
    'prov.sambanova.docs': 'مفتاح مجاني من community.sambanova.ai (بوابة المطوّرين، من غير بطاقة). موديلات مفتوحة سريعة؛ استخدم «تحميل الموديلات» تعرف الأسماء اللي مفتاحك يقدر يشغّلها.',
    'prov.sambanova.free_note': 'مفتاح مطوّر مجاني بحدود معدل سخية على الموديلات المفتوحة — تسجيل بإيميل من غير بطاقة.',
    'prov.huggingface.label': 'Hugging Face (حصة صغيرة)',
    'prov.huggingface.docs': 'توكن مجاني من huggingface.co/settings/tokens (صلاحية «Read» كفاية). أسماء الموديلات هي معرّفات المستودعات، مثال: meta-llama/Llama-3.3-70B-Instruct. وبعض الموديلات مقيّدة: افتح صفحتها مرة واحدة واقبل الترخيص. حصة شهرية مجانية صغيرة.',
    'prov.huggingface.free_note': 'مجاني بتوكن Hugging Face (صلاحية قراءة) — حصة شهرية صغيرة تكفي للتجربة والحركة الخفيفة.',
    'prov.pollinations.label': 'Pollinations (مش محتاج مفتاح)',
    'prov.pollinations.docs': '⚠️ نقطة وصول مجتمعية على أقصى تقدير: من غير تسجيل ومن غير مفتاح، بس حوالي طلب كل 30 ثانية لكل IP ومن غير أي ضمان استمرارية، فهي مناسبة للتجربة أكتر من متجر مشغول. رسائل العملاء بتروح لطرف تالت — ولو فيه حركة حقيقية حوّل لـ Google أو Groq أو Cerebras.',
    'prov.pollinations.free_note': 'من غير تسجيل ومن غير مفاتيح: بيشتغل في الحال أول ما تختاره. بس على أقصى تقدير — حوالي طلب كل 30 ثانية لكل IP.',
    'prov.openai.label': 'OpenAI (ChatGPT API)',
    'prov.openai.docs': 'مفتاح API بالدفع حسب الاستخدام من platform.openai.com — ومحتاج رصيد على الحساب (اشتراك ChatGPT Plus مش رصيد API). أفضل جودة وكمان تمثيلات قاعدة المعرفة. لسه من غير بطاقة أو رصيد؟ استخدم مزوّد 🆓.',
    'prov.anthropic.label': 'Anthropic (Claude)',
    'prov.anthropic.docs': 'مفتاح API من console.anthropic.com (محتاج رصيد على الحساب؛ واشتراك Claude مش رصيد API). قاعدة المعرفة بتستخدم البحث بالكلمات المفتاحية (Anthropic مفيش عنده API للتمثيلات).',
    'prov.deepseek.label': 'DeepSeek (رخيص جدًا)',
    'prov.deepseek.docs': 'مفتاح API رخيص جدًا من platform.deepseek.com — لازم تشحن الرصيد الأول قبل ما المفتاح يشتغل (كام دولار بيكفّوا مدة طويلة).',
    'prov.xai.label': 'xAI (Grok)',
    'prov.xai.docs': 'مفتاح API من console.x.ai. الحسابات الجديدة ساعات بياخدوا رصيد تجريبي صغير؛ وبعد كده بيبقى دفع حسب الاستخدام.',
    'prov.together.label': 'Together AI',
    'prov.together.docs': 'مفتاح API من api.together.xyz — ومحتاج حد أدنى من الشحن، فلو لسه مش عايز تدفع استخدم مزوّد 🆓.',
    'prov.custom.label': 'نقطة وصول مخصصة متوافقة مع OpenAI',
    'prov.custom.docs': 'أي سيرفر بيوفّر /chat/completions (بروكسي، أو موديل مستضاف عندك، أو مُجمّع، أو Cloudflare Workers AI). ابعت الـ Base URL واسم الموديل؛ والمفتاح اختياري.',
    'prov.omniroute.label': 'OmniRoute (بوابة على سيرفرك)',
    'prov.omniroute.docs': 'بوابة متوافقة مع OpenAI بتستضيفها بنفسك (github.com/diegosouzapw/OmniRoute). مفيش مفتاح ذكاء بيتخزن في البوت: OmniRoute هو اللي بيمسك حسابات المزوّدين ويوزّع الطلبات بينهم. شغّلها على نفس جهاز البوت (الافتراضي http://localhost:20128/v1)، أو وجّه البوت لمكان تاني بمتغيّر OMNIROUTE_BASE_URL. ولو إعدادات OmniRoute فيها REQUIRE_API_KEY=true، ابعت مفتاحها (OMNIROUTE_API_KEY).',
    'prov.ollama.label': 'Ollama (محلي، مجاني 100%)',
    'prov.ollama.docs': 'بيشتغل على جهازك: ثبّت Ollama، وبعدين `ollama pull llama3.2`. من غير مفتاح API ومن غير إنترنت — بس البوت لازم يشتغل على نفس الجهاز (أو تحدد الـ Base URL لعنوان الجهاز ده).',
    'prov.ollama.free_note': 'مجاني بالكامل وخصوصية كاملة — الموديل بيشتغل على جهازك. محتاج حوالي 8 جيجا رام لموديل صغير.',
    'prov.lmstudio.label': 'LM Studio (محلي، مجاني 100%)',
    'prov.lmstudio.docs': 'حمّل موديل في LM Studio وشغّل السيرفر المحلي بتاعه (البورت 1234)، وبعدين اختبر من هنا. مش محتاج مفتاح؛ والبوت لازم يشتغل على نفس الجهاز.',
    'prov.lmstudio.free_note': 'مجاني بالكامل وخصوصية كاملة — موديل محلي بواجهة ويندوز/ماك.',
    'prov.codex.label': 'اشتراك ChatGPT من خلال Codex CLI',
    'prov.codex.docs': 'بيستخدم `codex exec` بتسجيل دخول ChatGPT بتاعك (التثبيت: npm i -g @openai/codex، وبعدين `codex login`). بيستفيد من خطة ChatGPT اللي بتدفعها أصلاً — من غير مفتاح API. والبوت لازم يشتغل على الجهاز ده.',

    # =========================================================================
    # خدمات — ردود جاهزة وأخطاء الملفات و Codex
    # =========================================================================
    "kb.strict_no_info": "معنديش معلومات كفاية عن الموضوع ده في قاعدة المعرفة.",
    "biz.apology_default": (
        "آسف، عندي مشكلة في الرد دلوقتي. حد هيرجعلك قريب."
    ),
    "file.err.unsupported": "نوع الملف غير مدعوم. المسموح: {allowed}",
    "file.err.unsupported_type": "نوع الملف غير مدعوم: {suffix}",
    "file.err.empty": "الملف فاضي.",
    "file.err.too_large": "الملف كبير أوي (الحد الأقصى {mb} ميجا).",
    "file.err.unreadable": "معرفتش أقرأ '{name}' (غير مدعوم أو بايظ).",
    "file.err.no_text": (
        "مفيش نص مقروء في '{name}'. "
        "ملفات PDF المصوّرة أو الضوئية مش مدعومة (مفيش OCR)."
    ),
    "codex.err.not_installed": (
        "Codex CLI مش موجود. ثبّته (npm i -g @openai/codex) وشغّل `codex login`."
    ),
    "codex.err.bad_flags": (
        "Codex رفض فلاجات exec بتاعة إصدار الـ CLI عندك. حدّد CODEX_EXEC_ARGS "
        "في .env بالفلاجات اللي `codex exec` عندك بيقبلها (أو سيبها فاضية)."
    ),
    "codex.err.not_logged_in": "Codex مش عامل تسجيل دخول — شغّل `codex login` (Sign in with ChatGPT).",
    "codex.err.failed": "Codex فشل في توليد رد. راجع السجلات.",
    "codex.err.empty": "Codex رجّع رد فاضي.",

    # ==== append-below ====    # ==== append-below ====

    # =========================================================================
    # services/rules_service.py — قواعد الموضوعات والأسئلة بدون إجابة
    # =========================================================================
    "rule.status.rules": "قواعد الموضوعات: {count} مفعّلة",
    "rule.status.unanswered": "أسئلة بدون إجابة: {count}",
    "rule.status.resources": "المصادر: {count}",
    "rule.menu.title": "🧠 <b>التعليمات والقواعد</b>",
    "rule.menu.body": (
        "ابعتلي تعليماتك بأسلوبك — طريقة الرد، تقول إيه وما تقولوش، الأسعار، "
        "التوصيل، مواعيد العمل.\n"
        "أنا هقسّمها لـ <b>قواعد موضوعات</b> وأوريك مسودة: مفيش حاجة هتتطبّق "
        "غير لما تضغط ✅ اعتماد."
    ),
    "rule.menu.stats": "القواعد المفعّلة: <b>{rules}</b> · مسودات مستنية: <b>{drafts}</b>",
    "rule.menu.hint": (
        "لإضافة قواعد: ابعت النص على طول (أو /rules_add). "
        "أسئلة مستنية إجابة: {unanswered}."
    ),
    "rule.ask": "✍️ ابعت التعليمات دلوقتي (أو /cancel).",
    "rule.draft.title": "🧠 <b>مسودة القواعد — راجعها قبل التطبيق</b>",
    "rule.draft.count": "{count} قاعدة من نصك{ai}",
    "rule.draft.ai": " (مرتّبة بالذكاء الاصطناعي)",
    "rule.draft.plain": " (مقسّمة سطر سطر)",
    "rule.draft.questions": "❓ <b>محتاج توضيح في دي:</b>",
    "rule.draft.hint": "اضغط ✅ لتطبيقها على كل الردود، ✏️ لتعديلها، 🗑 لإلغائها.",
    "rule.draft.approved": "✅ اتطبّقت {count} قاعدة.",
    "rule.draft.rejected": "🗑 المسودة اتلغت ({count} قاعدة).",
    "rule.draft.gone": "المسودة دي مابقتش موجودة.",
    "rule.empty": "لسه مفيش قواعد. ابعت /rules_add بتعليماتك.",
    "rule.list.title": "🧠 <b>قواعد الموضوعات</b> ({count}) — اضغط للتشغيل/الإيقاف:",
    "rule.list.row": "{icon} #{id} <b>{topic}</b>",
    "rule.list.row_body": "    {rule}",
    "rule.toggled.on": "مفعّلة ✅",
    "rule.toggled.off": "متوقفة ⏸",
    "rule.deleted": "تم حذف القاعدة #{id}.",
    "rule.delete.missing": "مفيش قاعدة #{id}.",
    "rule.clear.ask": "أمسح <b>كل</b> القواعد ({count})؟",
    "rule.clear.done": "تم حذف {count} قاعدة.",
    "rule.disabled": (
        "قواعد الموضوعات متوقفة (/settings ← التعلّم والمصادر). "
        "القواعد محفوظة بس مش بتتبعت للموديل."
    ),
    "rule.cb.send": "ابعت التعليمات.",
    "rule.cb.step": "✍️ ابعت التعليمات دلوقتي (أو /cancel).",
    "rule.cb.approved": "اتطبّقت ✅",
    "rule.cb.rejected": "اتلغت 🗑",
    "rule.cb.toggled": "اتحدّثت",
    "rule.cb.not_found": "مش موجودة.",
    "rule.usage": "الاستخدام: /rules_add التعليمات",
    "rule.pending.empty": "مفيش نص أرتبه — جرّب تاني بنص.",
    # --- unanswered ---
    "unans.menu.title": "❓ <b>أسئلة معرفتش أرد عليها</b>",
    "unans.menu.none": "مفيش حاجة مستنية — المساعد رد على كل حاجة. 🎉",
    "unans.menu.count": "<b>{count}</b> سؤال مستني إجابتك.",
    "unans.menu.hint": "اضغط على السؤال، جاوب، والمساعد هيتعلم الإجابة للأبد.",
    "unans.row": "#{id} — {question}",
    "unans.card": (
        "❓ <b>سؤال #{id}</b>\n"
        "من: <b>{name}</b> (المحادثة <code>{chat_id}</code>)\n"
        "وقت السؤال: {when}\n\n"
        "<i>{question}</i>"
    ),
    "unans.notify": (
        "❓ <b>المساعد معرفش يرد</b>\n"
        "من: <b>{name}</b> (المحادثة <code>{chat_id}</code>)\n\n"
        "<i>{question}</i>\n\n"
        "ردّ على الرسالة دي بالإجابة وأنا هبعتها له وهحفظها. أو استخدم "
        "/unanswered تشوف القائمة."
    ),
    "unans.ask": "✍️ ابعت الإجابة على السؤال #{id} (أو /cancel).",
    "unans.asked": "ابعت الإجابة في رسالتك الجاية.",
    "unans.answered": "✅ الإجابة اتحفظت (#{id}) واتبعتت لصاحب السؤال.",
    "unans.answered_learned": "✅ اتحفظت واتستخدمت كرد جاهز (#{faq}).",
    "unans.answered_not_sent": "✅ الإجابة اتحفظت، بس معرفتش أوصّلها.",
    "unans.ignored": "اتجاهل.",
    "unans.gone": "السؤال ده مابقاش مستني.",
    "unans.empty_answer": "إجابة فاضية — ما اتحفظش حاجة.",
    "unans.deleted": "اتشال من القائمة.",
    "unans.clear.ask": "أمسح كل الأسئلة المستنية ({count})؟",
    "unans.clear.done": "تم مسح {count} سؤال.",
    "unans.auto_reply": "شكراً لسؤالك 🙏 سألت حد من الفريق وهيرد عليك في أقرب وقت.",

    # =========================================================================
    # services/resource_service.py — المصادر اللي المساعد يبحث فيها ويرشّحها
    # =========================================================================
    "res.status.summary": "المصادر: {total} ({links} رابط · {telegram} تيليجرام)",
    "res.menu.title": "📚 <b>المصادر</b>",
    "res.menu.body": (
        "ابعت رابط (موقع، منصة، جروب أو قناة تيليجرام) وأنا هقراه وأضيفه لقاعدة "
        "المعرفة وأستخدمه في الردود — يا إما كحقائق، يا إما كرابط أرشّحه للناس.\n\n"
        "الشكل: <code>https://example.com | العنوان | ملاحظة قصيرة</code> "
        "(العنوان والملاحظة اختياريين). والنص العادي ينفع برضه."
    ),
    "res.menu.empty": "لسه مفيش مصادر.",
    "res.menu.count": "<b>{count}</b> مصدر محفوظ — {telegram} تيليجرام و{links} رابط.",
    "res.menu.hint": "للإضافة: ابعت الرابط (أو /resources_add). للقائمة: /resources_list.",
    "res.ask": "🔗 ابعت الرابط (أو النص)، أو /cancel.",
    "res.cb.ask": "ابعت الرابط.",
    "res.added.link": "✅ تم حفظ <b>{title}</b>.\n{url}\n\n{read}",
    "res.added.read": "قريت {chars} حرف وضفتهم لقاعدة المعرفة — أقدر أقتبس منهم دلوقتي.",
    "res.added.unread": (
        "اتحفظ كمرجع. (معرفتش أقرأ الصفحة — روابط تيليجرام وبعض المواقع محتاجة "
        "متصفح؛ بس الرابط نفسه بيتستخدم في الردود.)"
    ),
    "res.added.telegram": (
        "✅ تم حفظ قناة/جروب تيليجرام: <b>{title}</b>\n{url}\n\n"
        "هوجّه الناس ليه لما يكون مناسب."
    ),
    "res.added.text": "✅ اتحفظ كمصدر نصي (<b>{title}</b>) — {chars} حرف.",
    "res.failed": "معرفتش أقرأ الرابط ده، بس حفظته كمرجع.",
    "res.empty_input": "مفيش حاجة تتحفظ — ابعت رابط أو نص.",
    "res.list.title": "📚 <b>المصادر</b> ({count}) — اضغط للتشغيل/الإيقاف:",
    "res.list.empty": "لسه مفيش مصادر. ابعت رابط، أو استخدم /resources_add.",
    "res.row.title": "#{id} <b>{title}</b>",
    "res.row.kind": "النوع: {kind}",
    "res.row.url": "الرابط: {url}",
    "res.row.notes": "ملاحظة: {notes}",
    "res.row.chars": "المقروء: {count} حرف",
    "res.row.disabled": "⏸ متوقف",
    "res.kind.link": "صفحة ويب",
    "res.kind.telegram": "قناة/جروب تيليجرام",
    "res.kind.text": "نص",
    "res.toggled.on": "مفعّل ✅",
    "res.toggled.off": "متوقف ⏸",
    "res.deleted": "تم حذف المصدر #{id}.",
    "res.delete.missing": "مفيش مصدر #{id}.",
    "res.clear.ask": "أمسح كل المصادر ({count})؟",
    "res.clear.done": "تم حذف {count} مصدر.",
    "res.usage": "الاستخدام: /resources_add الرابط أو النص",
    "res.disabled": (
        "المصادر متوقفة (/settings ← التعلّم والمصادر). "
        "المصادر محفوظة بس مش بتتبعت للموديل."
    ),

    # ==== append-below ====
}
