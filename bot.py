import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

import config
import database as dbm
from keyboards import (
    main_menu, library_menu, back_main_button, back_library_button,
    novels_list_keyboard, novel_page_keyboard, volume_view_keyboard,
    admin_menu, admin_novel_actions, admin_edit_fields, confirm_delete_keyboard,
    add_novel_form_keyboard, form_back_keyboard
)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== حالات المحادثة =====
(
    E_VALUE,
    RQ_WAIT, RP_WAIT, S_WAIT, B_WAIT,
    ADDVOL_NUM, ADDVOL_FILE,
    F_TITLE, F_AUTHOR, F_DESC, F_COVER, F_PDF,
) = range(12)


def is_admin(uid):
    return uid == config.ADMIN_ID


def escape_md(text):
    if not text: return ""
    for ch in ["_", "*", "[", "]", "`"]:
        text = text.replace(ch, f"\\{ch}")
    return text


def new_form():
    return {"title": "", "author": "", "description": "", "cover": None, "volumes": [], "next_vol": 1}


def render_form_text(form):
    lines = ["📝 **إضافة رواية جديدة**\n"]
    lines.append(f"📖 الاسم: {escape_md(form['title']) if form['title'] else '—'}")
    lines.append(f"✍️ المؤلف: {escape_md(form['author']) if form['author'] else '—'}")
    lines.append(f"📝 الوصف: {'✅' if form['description'] else '—'}")
    lines.append(f"🖼️ الغلاف: {'✅' if form['cover'] else '—'}")
    lines.append(f"\n📚 المجلدات: {len(form['volumes'])}")
    for v in form['volumes']:
        lines.append(f"  {'✅' if v.get('pdf') else '⏳'} المجلد {v['number']}")
    lines.append("\n✏️ اضغط على أي حقل لتعديله.")
    return "\n".join(lines)


# ===== أوامر =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    dbm.add_user(user.id, user.username or "", user.first_name or "")
    text = ("📚 **مكتبة فيستا**\n"
            "🅥 Vesta Library\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "مرحباً بك في أضخم مكتبة للروايات الآسيوية\n\n"
            "❝ اختر من القائمة أدناه للبدء ❞")
    if update.message:
        await update.message.reply_text(text, reply_markup=main_menu(), parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(text, reply_markup=main_menu(), parse_mode="Markdown")


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ هذا الأمر غير متاح."); return
    await update.message.reply_text("⚙️ **لوحة الإدارة**\nاختر ما تريد:", reply_markup=admin_menu(), parse_mode="Markdown")


# ===== معالج الأزرار الرئيسي =====
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    uid = q.from_user.id

    if data == "back_main":
        await start(update, context); return

    if data == "menu_library":
        await q.edit_message_text("📚 **المكتبة**\nاختر ما تريد:", reply_markup=library_menu(), parse_mode="Markdown"); return

    if data == "lib_novels":
        novels = dbm.get_all_novels()
        if not novels:
            await q.edit_message_text("📭 لا توجد روايات مضافة بعد.", reply_markup=back_library_button()); return
        await q.edit_message_text(f"📖 **الروايات** ({len(novels)} رواية)\nاختر رواية:",
            reply_markup=novels_list_keyboard(novels), parse_mode="Markdown"); return

    if data in ("lib_recent", "new_novels"):
        novels = dbm.get_new_novels(15)
        if not novels:
            await q.edit_message_text("📭 لا توجد روايات.", reply_markup=back_library_button()); return
        await q.edit_message_text("🆕 **أحدث الروايات:**", reply_markup=novels_list_keyboard(novels), parse_mode="Markdown"); return

    if data == "most_viewed":
        novels = dbm.get_most_viewed(15)
        await q.edit_message_text("🔥 **الأكثر مشاهدة:**",
            reply_markup=novels_list_keyboard(novels) if novels else back_main_button(), parse_mode="Markdown"); return

    if data == "top_rated":
        novels = dbm.get_top_rated(15)
        await q.edit_message_text("⭐ **الأعلى تقييمًا:**",
            reply_markup=novels_list_keyboard(novels) if novels else back_main_button(), parse_mode="Markdown"); return

    if data == "most_downloaded":
        novels = dbm.get_most_downloaded(15)
        await q.edit_message_text("🏆 **الأكثر تحميلاً:**",
            reply_markup=novels_list_keyboard(novels) if novels else back_main_button(), parse_mode="Markdown"); return

    if data == "trending":
        novels = dbm.get_most_viewed(10)
        await q.edit_message_text("📈 **الرائج هذا الأسبوع:**",
            reply_markup=novels_list_keyboard(novels) if novels else back_main_button(), parse_mode="Markdown"); return

    if data == "random_novel":
        n = dbm.get_random_novel()
        if not n:
            await q.edit_message_text("📭 لا توجد روايات.", reply_markup=back_main_button()); return
        await show_novel(q, n["id"]); return

    if data == "suggested":
        novels = dbm.get_top_rated(10)
        await q.edit_message_text("🎯 **مقترحة لك:**",
            reply_markup=novels_list_keyboard(novels) if novels else back_main_button(), parse_mode="Markdown"); return

    if data == "ai_recommend":
        await q.edit_message_text("✨ **رشح لي**\n\nالميزة قيد التطوير. حالياً يمكنك تصفح:\n• الأكثر مشاهدة\n• الأعلى تقييماً\n• المضافة حديثاً",
            reply_markup=back_main_button(), parse_mode="Markdown"); return

    if data == "smart_translate":
        await q.edit_message_text("🌐 خدمة الترجمة الذكية قيد التطوير.", reply_markup=back_main_button()); return

    if data == "about":
        await q.edit_message_text(
            "ℹ️ **حول البوت**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📚 **مكتبة فيستا**\n"
            "🅥 Vesta Library\n\n"
            "مكتبتك الشاملة للروايات الآسيوية\n"
            "بصيغة PDF عالية الجودة.\n\n"
            "🤖 بوت تيليجرام مجاني بالكامل\n"
            "💾 جميع الملفات محفوظة على تيليجرام",
            reply_markup=back_main_button(),
            parse_mode="Markdown"
        )
        return

    if data == "notifications":
        await q.edit_message_text("🔔 **التنبيهات**\n\nلتفعيل التنبيهات عند نزول مجلد جديد،\nأضف الرواية للمفضلة ❤️",
            reply_markup=back_main_button(), parse_mode="Markdown"); return

    if data.startswith("novel_"):
        nid = int(data.split("_")[1]); await show_novel(q, nid); return

    if data.startswith("vol_"):
        parts = data.split("_")
        nid, vnum = int(parts[1]), int(parts[2])
        vol = dbm.get_volume_by_number(nid, vnum)
        n = dbm.get_novel(nid)
        if not vol or not n:
            await q.edit_message_text("❌ المجلد غير موجود.", reply_markup=back_main_button()); return
        dbm.inc_downloads(nid); dbm.mark_read(uid, nid)
        caption = f"📕 **{escape_md(n['title'])}** — المجلد {vnum}"
        try:
            await q.message.reply_document(document=vol["pdf_file_id"], caption=caption,
                parse_mode="Markdown", reply_markup=volume_view_keyboard(nid))
            await q.answer("✅ تم إرسال الملف")
        except Exception as e:
            await q.answer(f"⚠️ خطأ: {e}", show_alert=True)
        return

    if data.startswith("fav_"):
        nid = int(data.split("_")[1])
        state = dbm.toggle_favorite(uid, nid)
        await q.answer("✅ أُضيفت للمفضلة" if state else "💔 أُزيلت من المفضلة")
        await show_novel(q, nid); return

    if data in ("favorites", "lib_favs"):
        favs = dbm.get_favorites(uid)
        if not favs:
            await q.edit_message_text("❤️ **المفضلة فارغة**\nأضف روايات لتراها هنا.",
                reply_markup=back_main_button(), parse_mode="Markdown"); return
        await q.edit_message_text(f"❤️ **مفضلاتك** ({len(favs)})",
            reply_markup=novels_list_keyboard(favs), parse_mode="Markdown"); return

    if data == "my_library":
        favs = dbm.get_favorites(uid)
        if not favs:
            await q.edit_message_text("📖 مكتبتك فارغة.", reply_markup=back_main_button()); return
        await q.edit_message_text("📖 **مكتبتك:**", reply_markup=novels_list_keyboard(favs), parse_mode="Markdown"); return

    if data == "my_stats":
        s = dbm.get_user_stats(uid)
        await q.edit_message_text(f"📊 **إحصائياتك**\n\n❤️ المفضلة: {s['favorites']}\n📖 روايات قرأتها: {s['reads']}",
            reply_markup=back_main_button(), parse_mode="Markdown"); return

    # ===== أزرار الإدارة العامة =====
    if data.startswith(("adm_", "confirm_del_")):
        if not is_admin(uid):
            await q.answer("⛔ لا تملك صلاحية.", show_alert=True); return
        return await handle_admin_buttons(q, context, data)


async def show_novel(q, nid):
    n = dbm.get_novel(nid)
    if not n:
        await q.edit_message_text("❌ الرواية غير موجودة.", reply_markup=back_main_button()); return
    dbm.inc_views(nid)
    vols = dbm.get_volumes(nid)
    is_fav = dbm.is_favorite(q.from_user.id, nid)
    text = (f"📖 **{escape_md(n['title'])}**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✍️ المؤلف: {escape_md(n['author'] or 'غير محدد')}\n"
            f"📚 عدد المجلدات: {len(vols)}\n")
    await q.edit_message_text(text, reply_markup=novel_page_keyboard(nid, vols, is_fav), parse_mode="Markdown")


async def handle_admin_buttons(q, context, data):
    if data == "adm_add_novel":
        context.user_data["form"] = new_form()
        form = context.user_data["form"]
        await q.edit_message_text(render_form_text(form), reply_markup=add_novel_form_keyboard(form), parse_mode="Markdown")
        return

    if data == "form_noop":
        return

    if data == "form_back":
        form = context.user_data.get("form")
        if not form:
            await q.edit_message_text("⚠️ الجلسة انتهت.", reply_markup=admin_menu()); return
        await q.edit_message_text(render_form_text(form), reply_markup=add_novel_form_keyboard(form), parse_mode="Markdown"); return

    if data == "form_cancel":
        context.user_data.pop("form", None)
        await q.edit_message_text("❌ تم الإلغاء.", reply_markup=admin_menu()); return

    if data.startswith("form_delvol_"):
        form = context.user_data.get("form")
        if not form:
            await q.edit_message_text("⚠️ الجلسة انتهت.", reply_markup=admin_menu()); return
        num = int(data.split("_")[2])
        form["volumes"] = [v for v in form["volumes"] if v["number"] != num]
        context.user_data["form"] = form
        await q.edit_message_text(render_form_text(form), reply_markup=add_novel_form_keyboard(form), parse_mode="Markdown"); return

    if data == "form_save":
        form = context.user_data.get("form")
        if not form:
            await q.edit_message_text("⚠️ الجلسة انتهت.", reply_markup=admin_menu()); return
        if not (form['title'] and form['author'] and form['volumes']):
            await q.answer("⚠️ املأ الحقول الأساسية.", show_alert=True); return
        nid = dbm.add_novel(form['title'], form['author'], "", form['description'], "", form['cover'])
        for v in form['volumes']:
            if v.get('pdf'):
                dbm.add_volume(nid, v['number'], v['pdf'])
        count = len(form['volumes'])
        context.user_data.pop("form", None)
        await q.edit_message_text(f"✅ تم حفظ الرواية (ID: {nid})\n📚 عدد المجلدات: {count}",
            reply_markup=admin_menu()); return

    if data == "adm_manage":
        novels = dbm.get_all_novels()
        if not novels:
            await q.edit_message_text("📭 لا توجد روايات.", reply_markup=admin_menu()); return
        await q.edit_message_text(f"📚 **إدارة المكتبة** ({len(novels)} رواية)\nاختر رواية:",
            reply_markup=novels_list_keyboard(novels, prefix="adm_novel"), parse_mode="Markdown"); return

    if data.startswith("adm_novel_"):
        nid = int(data.split("_")[2])
        n = dbm.get_novel(nid)
        if not n:
            await q.edit_message_text("❌ غير موجود.", reply_markup=admin_menu()); return
        await q.edit_message_text(f"⚙️ **إدارة:** {escape_md(n['title'])}\n\nاختر عملية:",
            reply_markup=admin_novel_actions(nid), parse_mode="Markdown"); return

    if data.startswith("adm_editnov_"):
        nid = int(data.split("_")[2])
        await q.edit_message_text("✏️ اختر الحقل:", reply_markup=admin_edit_fields(nid)); return

    if data.startswith("adm_delnov_"):
        nid = int(data.split("_")[2])
        n = dbm.get_novel(nid)
        if not n:
            await q.edit_message_text("❌ غير موجود.", reply_markup=admin_menu()); return
        await q.edit_message_text(f"⚠️ **تأكيد الحذف**\n\nهل تريد حذف **{escape_md(n['title'])}** مع جميع المجلدات؟",
            reply_markup=confirm_delete_keyboard(nid), parse_mode="Markdown"); return

    if data.startswith("confirm_del_"):
        nid = int(data.split("_")[2])
        dbm.delete_novel(nid)
        await q.edit_message_text("✅ تم حذف الرواية.", reply_markup=admin_menu()); return

    if data.startswith("adm_showvols_"):
        nid = int(data.split("_")[2])
        vols = dbm.get_volumes(nid)
        if not vols:
            await q.edit_message_text("📭 لا توجد مجلدات.", reply_markup=admin_novel_actions(nid)); return
        text = "📕 **المجلدات:**\n\n"
        for v in vols:
            text += f"• المجلد {v['volume_number']}\n"
        await q.edit_message_text(text, reply_markup=admin_novel_actions(nid), parse_mode="Markdown"); return

    if data == "adm_edit":
        novels = dbm.get_all_novels()
        if not novels:
            await q.edit_message_text("📭 لا توجد روايات.", reply_markup=admin_menu()); return
        await q.edit_message_text("✏️ اختر رواية:", reply_markup=novels_list_keyboard(novels, prefix="adm_editnov")); return

    if data == "adm_delete":
        novels = dbm.get_all_novels()
        if not novels:
            await q.edit_message_text("📭 لا توجد روايات.", reply_markup=admin_menu()); return
        await q.edit_message_text("🗑 اختر رواية:", reply_markup=novels_list_keyboard(novels, prefix="adm_delnov")); return

    if data == "adm_stats":
        stats = (f"📊 **إحصائيات مكتبة فيستا**\n━━━━━━━━━━━━━━━━━━━━\n"
                 f"👥 المستخدمون: {dbm.count_users()}\n"
                 f"📚 الروايات: {len(dbm.get_all_novels())}\n"
                 f"📥 الطلبات: {dbm.count_requests()}\n"
                 f"⚠️ البلاغات: {dbm.count_reports()}")
        await q.edit_message_text(stats, reply_markup=admin_menu(), parse_mode="Markdown"); return


# ===== دوال دخول الحوارات (Entry Points) =====
async def form_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    form = context.user_data.get("form")
    if not form:
        await q.edit_message_text("⚠️ الجلسة انتهت. ابدأ من جديد.", reply_markup=admin_menu())
        return ConversationHandler.END

    if data == "form_e_title":
        await q.edit_message_text("📖 أرسل اسم الرواية:", reply_markup=form_back_keyboard())
        return F_TITLE
    if data == "form_e_author":
        await q.edit_message_text("✍️ أرسل اسم المؤلف:", reply_markup=form_back_keyboard())
        return F_AUTHOR
    if data == "form_e_desc":
        await q.edit_message_text("📝 أرسل وصف الرواية:", reply_markup=form_back_keyboard())
        return F_DESC
    if data == "form_e_cover":
        await q.edit_message_text("🖼️ أرسل صورة الغلاف:", reply_markup=form_back_keyboard())
        return F_COVER
    if data == "form_addvol":
        num = form["next_vol"]
        form["volumes"].append({"number": num, "pdf": None})
        form["next_vol"] += 1
        context.user_data["form"] = form
        context.user_data["up_vol"] = num
        await q.edit_message_text(f"📕 أرسل ملف PDF للمجلد {num}:", reply_markup=form_back_keyboard())
        return F_PDF
    if data.startswith("form_up_"):
        num = int(data.split("_")[2])
        context.user_data["up_vol"] = num
        await q.edit_message_text(f"📕 أرسل ملف PDF للمجلد {num}:", reply_markup=form_back_keyboard())
        return F_PDF
    return ConversationHandler.END


async def addvol_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    nid = int(q.data.split("_")[2])
    context.user_data["add_vol_nid"] = nid
    await q.edit_message_text("➕ **إضافة مجلد**\n\nأرسل رقم المجلد:\n_(/cancel للإلغاء)_")
    return ADDVOL_NUM


async def edit_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("_")
    nid = int(parts[1])
    field = parts[2]
    context.user_data["edit_nid"] = nid
    context.user_data["edit_field"] = field
    labels = {"title": "الاسم", "author": "المؤلف", "description": "الوصف"}
    await q.edit_message_text(f"✏️ أرسل القيمة الجديدة لـ **{labels.get(field, field)}**:\n_(/cancel)_", parse_mode="Markdown")
    return E_VALUE


async def broadcast_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("📢 **إرسال إعلان**\n\nأرسل الرسالة:\n_(/cancel)_")
    return B_WAIT


# ===== Handlers الحوارات =====
async def form_title(update, context):
    form = context.user_data.get("form")
    if not form: return ConversationHandler.END
    form["title"] = update.message.text.strip()
    context.user_data["form"] = form
    await update.message.reply_text(render_form_text(form), reply_markup=add_novel_form_keyboard(form), parse_mode="Markdown")
    return ConversationHandler.END


async def form_author(update, context):
    form = context.user_data.get("form")
    if not form: return ConversationHandler.END
    form["author"] = update.message.text.strip()
    context.user_data["form"] = form
    await update.message.reply_text(render_form_text(form), reply_markup=add_novel_form_keyboard(form), parse_mode="Markdown")
    return ConversationHandler.END


async def form_desc(update, context):
    form = context.user_data.get("form")
    if not form: return ConversationHandler.END
    form["description"] = update.message.text.strip()
    context.user_data["form"] = form
    await update.message.reply_text(render_form_text(form), reply_markup=add_novel_form_keyboard(form), parse_mode="Markdown")
    return ConversationHandler.END


async def form_cover(update, context):
    form = context.user_data.get("form")
    if not form: return ConversationHandler.END
    if not update.message.photo:
        await update.message.reply_text("❌ أرسل صورة.")
        return F_COVER
    form["cover"] = update.message.photo[-1].file_id
    context.user_data["form"] = form
    await update.message.reply_text(render_form_text(form), reply_markup=add_novel_form_keyboard(form), parse_mode="Markdown")
    return ConversationHandler.END


async def form_pdf(update, context):
    form = context.user_data.get("form")
    if not form: return ConversationHandler.END
    if not update.message.document:
        await update.message.reply_text("❌ أرسل ملف PDF.")
        return F_PDF
    num = context.user_data.get("up_vol")
    for v in form["volumes"]:
        if v["number"] == num:
            v["pdf"] = update.message.document.file_id
            break
    context.user_data["form"] = form
    await update.message.reply_text(f"✅ تم رفع PDF للمجلد {num}.\n\n" + render_form_text(form),
        reply_markup=add_novel_form_keyboard(form), parse_mode="Markdown")
    return ConversationHandler.END


async def addvol_num(update, context):
    try:
        num = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ أرسل رقماً.")
        return ADDVOL_NUM
    context.user_data["addvol_num"] = num
    await update.message.reply_text("📄 أرسل ملف PDF:")
    return ADDVOL_FILE


async def addvol_file(update, context):
    if not update.message.document:
        await update.message.reply_text("❌ أرسل PDF.")
        return ADDVOL_FILE
    nid = context.user_data["add_vol_nid"]
    num = context.user_data["addvol_num"]
    dbm.add_volume(nid, num, update.message.document.file_id)
    await update.message.reply_text(f"✅ تم إضافة المجلد {num}.", reply_markup=admin_menu())
    return ConversationHandler.END


async def edit_value(update, context):
    dbm.update_novel_field(context.user_data["edit_nid"], context.user_data["edit_field"], update.message.text)
    await update.message.reply_text("✅ تم التعديل.", reply_markup=admin_menu())
    return ConversationHandler.END


async def broadcast_wait(update, context):
    msg = update.message.text
    users = dbm.get_all_users()
    sent = 0
    await update.message.reply_text(f"⏳ إرسال إلى {len(users)} مستخدم...")
    for uid in users:
        try:
            await context.bot.send_message(uid, f"📢 **إعلان من مكتبة فيستا:**\n\n{msg}", parse_mode="Markdown")
            sent += 1
        except Exception:
            pass
    await update.message.reply_text(f"✅ تم إلى {sent}/{len(users)}.", reply_markup=admin_menu())
    return ConversationHandler.END


async def request_novel_start(update, context):
    q = update.callback_query; await q.answer()
    await q.edit_message_text("📥 **طلب رواية**\n\nأرسل اسم الرواية:\n_(/cancel)_", parse_mode="Markdown")
    return RQ_WAIT


async def request_novel_wait(update, context):
    user = update.effective_user
    content = update.message.text
    dbm.add_request(user.id, content)
    try:
        await context.bot.send_message(config.ADMIN_ID,
            f"📥 **طلب رواية جديد**\n\n👤 {user.first_name} (@{user.username or 'بدون'})\n🆔 `{user.id}`\n\n📖 {content}",
            parse_mode="Markdown")
    except Exception as e:
        logger.error(e)
    await update.message.reply_text("✅ تم الإرسال.", reply_markup=main_menu())
    return ConversationHandler.END


async def report_start(update, context):
    q = update.callback_query; await q.answer()
    await q.edit_message_text("⚠️ **إبلاغ**\n\nأرسل التفاصيل:\n_(/cancel)_", parse_mode="Markdown")
    return RP_WAIT


async def report_wait(update, context):
    user = update.effective_user
    content = update.message.text
    dbm.add_report(user.id, content)
    try:
        await context.bot.send_message(config.ADMIN_ID,
            f"⚠️ **بلاغ جديد**\n\n👤 {user.first_name} (@{user.username or 'بدون'})\n🆔 `{user.id}`\n\n📝 {content}",
            parse_mode="Markdown")
    except Exception as e:
        logger.error(e)
    await update.message.reply_text("✅ تم الإرسال.", reply_markup=main_menu())
    return ConversationHandler.END


async def search_start(update, context):
    q = update.callback_query; await q.answer()
    await q.edit_message_text("🔎 **البحث**\n\nأرسل اسم الرواية أو المؤلف:\n_(/cancel)_", parse_mode="Markdown")
    return S_WAIT


async def search_wait(update, context):
    results = dbm.search_novels(update.message.text)
    if not results:
        await update.message.reply_text("❌ لا نتائج.", reply_markup=main_menu())
        return ConversationHandler.END
    await update.message.reply_text(f"✅ {len(results)} نتيجة:", reply_markup=novels_list_keyboard(results))
    return ConversationHandler.END


async def cancel(update, context):
    await update.message.reply_text("❌ تم الإلغاء.", reply_markup=main_menu())
    return ConversationHandler.END


# ===== تهيئة التطبيق (module-level for Webhook) =====
dbm.init_db()
application = Application.builder().token(config.BOT_TOKEN).build()

# 1. الأوامر
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("admin", admin_cmd))

# 2. الحوارات (ConversationHandlers)
form_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(form_entry, pattern="^(form_e_|form_addvol|form_up_)")],
    states={
        F_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, form_title)],
        F_AUTHOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, form_author)],
        F_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, form_desc)],
        F_COVER: [MessageHandler(filters.PHOTO, form_cover)],
        F_PDF: [MessageHandler(filters.Document.PDF, form_pdf)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    per_message=False,
    allow_reentry=True,
)

add_vol_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(addvol_entry, pattern="^adm_addvol_")],
    states={
        ADDVOL_NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, addvol_num)],
        ADDVOL_FILE: [MessageHandler(filters.Document.PDF, addvol_file)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    per_message=False,
    allow_reentry=True,
)

edit_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(edit_entry, pattern="^editf_")],
    states={E_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_value)]},
    fallbacks=[CommandHandler("cancel", cancel)],
    per_message=False,
    allow_reentry=True,
)

broadcast_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(broadcast_entry, pattern="^adm_broadcast$")],
    states={B_WAIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_wait)]},
    fallbacks=[CommandHandler("cancel", cancel)],
    per_message=False,
    allow_reentry=True,
)

request_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(request_novel_start, pattern="^request_novel$")],
    states={RQ_WAIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, request_novel_wait)]},
    fallbacks=[CommandHandler("cancel", cancel)],
    per_message=False,
    allow_reentry=True,
)

report_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(report_start, pattern="^report$")],
    states={RP_WAIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, report_wait)]},
    fallbacks=[CommandHandler("cancel", cancel)],
    per_message=False,
    allow_reentry=True,
)

search_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(search_start, pattern="^(search_start|lib_search)$")],
    states={S_WAIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_wait)]},
    fallbacks=[CommandHandler("cancel", cancel)],
    per_message=False,
    allow_reentry=True,
)

application.add_handler(form_conv)
application.add_handler(add_vol_conv)
application.add_handler(edit_conv)
application.add_handler(broadcast_conv)
application.add_handler(request_conv)
application.add_handler(report_conv)
application.add_handler(search_conv)

# 3. المعالج العام للأزرار (في النهاية)
application.add_handler(CallbackQueryHandler(buttons))
