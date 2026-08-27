"""Textos de emails transaccionals de client (routers/auth.py, erp.py,
admin.py, tasks/peticiones.py, services/orders.py), llegits amb
services/i18n.translate(). Claus "grosses" (email sencer, no frase a frase):
és així com es tradueix de veritat un email i evita compondre HTML trencat
combinant micro-claus.

Font canònica: `services/i18n.translate()` cau aquí si la taula `translations`
no té la clau (p. ex. abans d'executar `scripts/seed_translations.py`, o en
tests amb BD buida) — mai s'envia un email amb la clau crua com a text.
`scripts/seed_translations.py` importa aquest mateix diccionari per sembrar
la BD (que és la font que fa servir realment l'admin per editar-los).
"""

EMAIL_TRANSLATIONS: dict[str, dict[str, str]] = {
    "email.verify_email.subject": {
        "ca": "Confirma el teu email — {nom}",
        "es": "Confirma tu email — {nom}",
        "en": "Confirm your email — {nom}",
    },
    "email.verify_email.body_text": {
        "ca": (
            "Benvingut/da a {nom}!\n\n"
            "Confirma el teu email per activar el compte (enllaç vàlid {hours}h):\n\n{link}\n\n"
            "Amb el compte actiu podràs:\n"
            "- Demanar discos que ara mateix no tenim en estoc: t'avisem per email en el moment que arribin.\n"
            "- Connectar el teu Spotify per rebre recomanacions del catàleg segons el que escoltes.\n"
            "- Consultar l'estat de les teves comandes i gestionar les adreces d'enviament.\n\n"
            "Si no has creat aquest compte, ignora aquest correu.\n"
        ),
        "es": (
            "¡Bienvenido/a a {nom}!\n\n"
            "Confirma tu email para activar la cuenta (enlace válido {hours}h):\n\n{link}\n\n"
            "Con la cuenta activa podrás:\n"
            "- Pedir discos que ahora mismo no tenemos en stock: te avisamos por email en cuanto lleguen.\n"
            "- Conectar tu Spotify para recibir recomendaciones del catálogo según lo que escuchas.\n"
            "- Consultar el estado de tus pedidos y gestionar las direcciones de envío.\n\n"
            "Si no has creado esta cuenta, ignora este correo.\n"
        ),
        "en": (
            "Welcome to {nom}!\n\n"
            "Confirm your email to activate your account (link valid for {hours}h):\n\n{link}\n\n"
            "With an active account you can:\n"
            "- Request records we don't have in stock right now: we'll email you the moment they arrive.\n"
            "- Connect your Spotify to get catalogue recommendations based on what you listen to.\n"
            "- Check your order status and manage your shipping addresses.\n\n"
            "If you didn't create this account, ignore this email.\n"
        ),
    },
    "email.verify_email.heading": {
        "ca": "Benvingut/da a {nom}!",
        "es": "¡Bienvenido/a a {nom}!",
        "en": "Welcome to {nom}!",
    },
    "email.verify_email.body_html": {
        "ca": (
            '<p style="font-size:14px;line-height:1.5">Confirma el teu email per activar el compte i començar a fer servir la botiga.</p>'
            '<p style="font-size:12px;color:#71717a">L\'enllaç caduca en {hours}h. Si el botó no funciona, copia aquest enllaç al navegador:<br>'
            '<a href="{link}" style="color:#f59e0b">{link}</a></p>'
            '<hr style="border:none;border-top:1px solid #e4e4e7;margin:24px 0">'
            '<p style="font-size:14px;line-height:1.6">Amb el compte actiu podràs:</p>'
            '<ul style="font-size:14px;line-height:1.6;padding-left:18px">'
            "<li><strong>Demanar discos</strong> que ara mateix no tenim en estoc: t'avisem per email en el moment que arribin.</li>"
            "<li><strong>Connectar Spotify</strong> per rebre recomanacions del catàleg segons el que escoltes.</li>"
            "<li>Consultar l'estat de les teves comandes i gestionar les adreces d'enviament.</li></ul>"
            '<p style="font-size:12px;color:#a1a1aa;margin-top:24px">Si no has creat aquest compte, ignora aquest correu.</p>'
        ),
        "es": (
            '<p style="font-size:14px;line-height:1.5">Confirma tu email para activar la cuenta y empezar a usar la tienda.</p>'
            '<p style="font-size:12px;color:#71717a">El enlace caduca en {hours}h. Si el botón no funciona, copia este enlace en el navegador:<br>'
            '<a href="{link}" style="color:#f59e0b">{link}</a></p>'
            '<hr style="border:none;border-top:1px solid #e4e4e7;margin:24px 0">'
            '<p style="font-size:14px;line-height:1.6">Con la cuenta activa podrás:</p>'
            '<ul style="font-size:14px;line-height:1.6;padding-left:18px">'
            "<li><strong>Pedir discos</strong> que ahora mismo no tenemos en stock: te avisamos por email en cuanto lleguen.</li>"
            "<li><strong>Conectar Spotify</strong> para recibir recomendaciones del catálogo según lo que escuchas.</li>"
            "<li>Consultar el estado de tus pedidos y gestionar las direcciones de envío.</li></ul>"
            '<p style="font-size:12px;color:#a1a1aa;margin-top:24px">Si no has creado esta cuenta, ignora este correo.</p>'
        ),
        "en": (
            '<p style="font-size:14px;line-height:1.5">Confirm your email to activate your account and start using the shop.</p>'
            '<p style="font-size:12px;color:#71717a">The link expires in {hours}h. If the button doesn\'t work, copy this link into your browser:<br>'
            '<a href="{link}" style="color:#f59e0b">{link}</a></p>'
            '<hr style="border:none;border-top:1px solid #e4e4e7;margin:24px 0">'
            '<p style="font-size:14px;line-height:1.6">With an active account you can:</p>'
            '<ul style="font-size:14px;line-height:1.6;padding-left:18px">'
            "<li><strong>Request records</strong> we don't have in stock right now: we'll email you the moment they arrive.</li>"
            "<li><strong>Connect Spotify</strong> to get catalogue recommendations based on what you listen to.</li>"
            "<li>Check your order status and manage your shipping addresses.</li></ul>"
            '<p style="font-size:12px;color:#a1a1aa;margin-top:24px">If you didn\'t create this account, ignore this email.</p>'
        ),
    },
    "email.verify_email.cta": {
        "ca": "Confirma el teu email", "es": "Confirma tu email", "en": "Confirm your email",
    },
    "email.magic_link.subject": {
        "ca": "El teu enllaç d'accés — {nom}",
        "es": "Tu enlace de acceso — {nom}",
        "en": "Your access link — {nom}",
    },
    "email.magic_link.body_text": {
        "ca": "Entra a la botiga amb aquest enllaç (caduca en {minuts} min):\n\n{link}\n",
        "es": "Entra en la tienda con este enlace (caduca en {minuts} min):\n\n{link}\n",
        "en": "Log in to the shop with this link (expires in {minuts} min):\n\n{link}\n",
    },
    "email.magic_link.heading": {
        "ca": "El teu enllaç d'accés", "es": "Tu enlace de acceso", "en": "Your access link",
    },
    "email.magic_link.body_html": {
        "ca": '<p style="font-size:14px;line-height:1.5">Entra a la botiga amb un clic, sense contrasenya. L\'enllaç caduca en {minuts} minuts.</p>',
        "es": '<p style="font-size:14px;line-height:1.5">Entra en la tienda con un clic, sin contraseña. El enlace caduca en {minuts} minutos.</p>',
        "en": '<p style="font-size:14px;line-height:1.5">Log in to the shop with one click, no password. The link expires in {minuts} minutes.</p>',
    },
    "email.magic_link.cta": {
        "ca": "Entra a la botiga", "es": "Entra en la tienda", "en": "Log in to the shop",
    },
    "email.order_confirmed.subject": {
        "ca": "Comanda confirmada #{order_short} — {nom}",
        "es": "Pedido confirmado #{order_short} — {nom}",
        "en": "Order confirmed #{order_short} — {nom}",
    },
    "email.order_confirmed.body_text": {
        "ca": (
            "Gràcies per la teva compra! Hem confirmat el pagament i estem preparant la comanda.\n"
            "Total: {total} EUR\nSegueix-la aquí: {link}\n"
        ),
        "es": (
            "¡Gracias por tu compra! Hemos confirmado el pago y estamos preparando el pedido.\n"
            "Total: {total} EUR\nSíguelo aquí: {link}\n"
        ),
        "en": (
            "Thanks for your purchase! We've confirmed the payment and are preparing your order.\n"
            "Total: {total} EUR\nTrack it here: {link}\n"
        ),
    },
    "email.order_confirmed.heading": {
        "ca": "Comanda confirmada!", "es": "¡Pedido confirmado!", "en": "Order confirmed!",
    },
    "email.order_confirmed.body_html": {
        "ca": (
            '<p style="font-size:14px;line-height:1.5">Gràcies per la teva compra! Hem confirmat el pagament i estem preparant la comanda.</p>'
            '<p style="font-size:14px;line-height:1.5"><strong>Total: {total} €</strong></p>'
        ),
        "es": (
            '<p style="font-size:14px;line-height:1.5">¡Gracias por tu compra! Hemos confirmado el pago y estamos preparando el pedido.</p>'
            '<p style="font-size:14px;line-height:1.5"><strong>Total: {total} €</strong></p>'
        ),
        "en": (
            '<p style="font-size:14px;line-height:1.5">Thanks for your purchase! We\'ve confirmed the payment and are preparing your order.</p>'
            '<p style="font-size:14px;line-height:1.5"><strong>Total: {total} €</strong></p>'
        ),
    },
    "email.order_confirmed.cta": {
        "ca": "Veure la comanda", "es": "Ver el pedido", "en": "View order",
    },
    "email.order_ready_pickup.subject": {
        "ca": "Ja pots venir a recollir la teva comanda — {nom}",
        "es": "Ya puedes venir a recoger tu pedido — {nom}",
        "en": "You can now come pick up your order — {nom}",
    },
    "email.order_ready_pickup.body_text": {
        "ca": (
            "La teva comanda #{order_short} ja està preparada a la botiga: pots passar a recollir-la "
            "quan vulguis dins del nostre horari.\nDetalls: {link}\n"
        ),
        "es": (
            "Tu pedido #{order_short} ya está preparado en la tienda: puedes pasar a recogerlo "
            "cuando quieras dentro de nuestro horario.\nDetalles: {link}\n"
        ),
        "en": (
            "Your order #{order_short} is ready at the shop: come pick it up whenever "
            "suits you within our opening hours.\nDetails: {link}\n"
        ),
    },
    "email.order_ready_pickup.heading": {
        "ca": "Ja la pots recollir!", "es": "¡Ya lo puedes recoger!", "en": "Ready for pickup!",
    },
    "email.order_ready_pickup.body_html": {
        "ca": '<p style="font-size:14px;line-height:1.5">La teva comanda <strong>#{order_short}</strong> ja està preparada a la botiga: pots passar a recollir-la quan vulguis dins del nostre horari.</p>',
        "es": '<p style="font-size:14px;line-height:1.5">Tu pedido <strong>#{order_short}</strong> ya está preparado en la tienda: puedes pasar a recogerlo cuando quieras dentro de nuestro horario.</p>',
        "en": '<p style="font-size:14px;line-height:1.5">Your order <strong>#{order_short}</strong> is ready at the shop: come pick it up whenever suits you within our opening hours.</p>',
    },
    "email.order_ready_pickup.cta": {
        "ca": "Veure la comanda", "es": "Ver el pedido", "en": "View order",
    },
    "email.peticion_price_ready.subject": {
        "ca": 'Ja tenim preu per "{disco}"', "es": 'Ya tenemos precio para "{disco}"', "en": 'We have a price for "{disco}"',
    },
    "email.peticion_price_ready.body_text": {
        "ca": (
            "Hola {nombre},\n\nHem trobat \"{disco}\", que ens vas demanar. Costa {precio} €.\n"
            "Accepta'l o rebutja'l aquí (enllaç d'accés directe, vàlid 14 dies): {link}\n\n{nom}"
        ),
        "es": (
            "Hola {nombre},\n\nHemos encontrado \"{disco}\", que nos pediste. Cuesta {precio} €.\n"
            "Acéptalo o recházalo aquí (enlace de acceso directo, válido 14 días): {link}\n\n{nom}"
        ),
        "en": (
            "Hi {nombre},\n\nWe've found \"{disco}\", which you requested. It costs €{precio}.\n"
            "Accept or decline it here (direct access link, valid 14 days): {link}\n\n{nom}"
        ),
    },
    "email.peticion_price_ready.heading": {
        "ca": "Ja tenim preu!", "es": "¡Ya tenemos precio!", "en": "We have a price!",
    },
    "email.peticion_price_ready.body_html": {
        "ca": (
            '<p style="font-size:14px;line-height:1.5">Hem trobat <strong>"{disco}"</strong>, que ens vas demanar.</p>'
            '<p style="font-size:14px;line-height:1.5">Costa <strong>{precio} €</strong>. Accepta\'l o rebutja\'l des del teu compte abans que en fem la comanda.</p>'
        ),
        "es": (
            '<p style="font-size:14px;line-height:1.5">Hemos encontrado <strong>"{disco}"</strong>, que nos pediste.</p>'
            '<p style="font-size:14px;line-height:1.5">Cuesta <strong>{precio} €</strong>. Acéptalo o recházalo desde tu cuenta antes de que hagamos el pedido.</p>'
        ),
        "en": (
            '<p style="font-size:14px;line-height:1.5">We\'ve found <strong>"{disco}"</strong>, which you requested.</p>'
            '<p style="font-size:14px;line-height:1.5">It costs <strong>€{precio}</strong>. Accept or decline it from your account before we order it.</p>'
        ),
    },
    "email.peticion_price_ready.cta": {
        "ca": "Accepta o rebutja", "es": "Acepta o rechaza", "en": "Accept or decline",
    },
    "email.peticion_arrived.subject": {
        "ca": '"{disco}" ja és a la botiga', "es": '"{disco}" ya está en la tienda', "en": '"{disco}" is now in stock',
    },
    "email.peticion_arrived.heading": {
        "ca": "Ja el tenim!", "es": "¡Ya lo tenemos!", "en": "It's arrived!",
    },
    "email.peticion_arrived.cta": {
        "ca": "Anar a les meves peticions", "es": "Ir a mis peticiones", "en": "Go to my requests",
    },
    "email.peticion_arrived.paid_ship": {
        "ca": 'Ja tenim "{disco}"! Com que ja el vas pagar, no has de fer res més: l\'enviarem en breu.',
        "es": '¡Ya tenemos "{disco}"! Como ya lo pagaste, no tienes que hacer nada más: lo enviaremos en breve.',
        "en": 'We now have "{disco}"! Since you already paid for it, there\'s nothing else to do: we\'ll ship it shortly.',
    },
    "email.peticion_arrived.paid_pickup": {
        "ca": 'Ja tenim "{disco}"! Com que ja el vas pagar, no has de fer res més: ja el pots venir a recollir.',
        "es": '¡Ya tenemos "{disco}"! Como ya lo pagaste, no tienes que hacer nada más: ya puedes venir a recogerlo.',
        "en": 'We now have "{disco}"! Since you already paid for it, there\'s nothing else to do: you can come pick it up now.',
    },
    "email.peticion_arrived.pay_in_store": {
        "ca": 'Ja tenim "{disco}" a la botiga! Te l\'hem reservat 72 hores: vine a recollir-lo i pagar-lo abans que caduqui la reserva. Detalls: {link}',
        "es": '¡Ya tenemos "{disco}" en la tienda! Te lo hemos reservado 72 horas: ven a recogerlo y pagarlo antes de que caduque la reserva. Detalles: {link}',
        "en": 'We now have "{disco}" at the shop! We\'ve held it for you for 72 hours: come pick it up and pay before the reservation expires. Details: {link}',
    },
    "email.peticion_arrived.complete_ship": {
        "ca": 'Ja tenim "{disco}"! Completa la compra aquí (l\'enviament): {link}',
        "es": '¡Ya tenemos "{disco}"! Completa la compra aquí (el envío): {link}',
        "en": 'We now have "{disco}"! Complete your purchase here (shipping): {link}',
    },
    "email.peticion_arrived.complete_pickup": {
        "ca": 'Ja tenim "{disco}"! Completa la compra aquí (la recollida): {link}',
        "es": '¡Ya tenemos "{disco}"! Completa la compra aquí (la recogida): {link}',
        "en": 'We now have "{disco}"! Complete your purchase here (pickup): {link}',
    },
    "email.peticion_reserva_alliberada.subject": {
        "ca": 'S\'ha alliberat la reserva de "{disco}"',
        "es": 'Se ha liberado la reserva de "{disco}"',
        "en": 'The reservation for "{disco}" has been released',
    },
    "email.peticion_reserva_alliberada.heading": {
        "ca": "S'ha alliberat la reserva", "es": "Se ha liberado la reserva", "en": "Reservation released",
    },
    "email.peticion_reserva_alliberada.cta": {
        "ca": "Torna a demanar-lo", "es": "Vuelve a pedirlo", "en": "Request it again",
    },
    "email.peticion_reserva_alliberada.motiu_paga_botiga": {
        "ca": 'No vas passar a recollir "{disco}" dins de les 72 hores de reserva, així que ha tornat a la venda general.',
        "es": 'No pasaste a recoger "{disco}" dentro de las 72 horas de reserva, así que ha vuelto a la venta general.',
        "en": 'You didn\'t come pick up "{disco}" within the 72-hour reservation window, so it\'s back on general sale.',
    },
    "email.peticion_reserva_alliberada.motiu_altres": {
        "ca": 'No vas acabar de completar la compra de "{disco}" a temps, així que l\'exemplar ha tornat a la venda general.',
        "es": 'No terminaste de completar la compra de "{disco}" a tiempo, así que el ejemplar ha vuelto a la venta general.',
        "en": 'You didn\'t finish completing the purchase of "{disco}" in time, so the copy is back on general sale.',
    },
    "email.peticion_reserva_alliberada.body_text": {
        "ca": "Hola {nombre},\n\n{motiu} Si encara el vols, torna a demanar-lo: {link}\n\n{nom}",
        "es": "Hola {nombre},\n\n{motiu} Si todavía lo quieres, vuelve a pedirlo: {link}\n\n{nom}",
        "en": "Hi {nombre},\n\n{motiu} If you still want it, request it again: {link}\n\n{nom}",
    },
    "email.peticion_reserva_alliberada.body_html": {
        "ca": '<p style="font-size:14px;line-height:1.5">{motiu} Si encara el vols, torna a demanar-lo.</p>',
        "es": '<p style="font-size:14px;line-height:1.5">{motiu} Si todavía lo quieres, vuelve a pedirlo.</p>',
        "en": '<p style="font-size:14px;line-height:1.5">{motiu} If you still want it, request it again.</p>',
    },
}
