"""Plantillas legales en castellano e inglés (el catalán vive en seed_legal_pages.py).

Mismos marcadores que las plantillas catalanas ({nom}, {nif}, {adreca}, {email},
{telefon}) y mismo criterio: PLANTILLA razonable, NO sustituye la revisión de un
abogado/gestor. Los enlaces internos llevan el prefijo de idioma (`/es/...`) porque
el contenido es HTML crudo y el sitio usa `localePrefix: 'always'`.

Estructura: {slug_base: (nombre_de_la_página, html)}. En la BD se guardan con slug
`<slug_base>-es` / `<slug_base>-en`; la ruta [pagina] del front sirve la del idioma
activo (ver web/app/[locale]/[pagina]/page.jsx).
"""

ES_PAGES = {
    "avis-legal": ("Aviso legal", """
<p>En cumplimiento del artículo 10 de la Ley 34/2002, de servicios de la sociedad de la
información y de comercio electrónico (LSSI-CE), se informa de que este sitio web es
titularidad de:</p>

<ul>
  <li><strong>Titular:</strong> {nom}</li>
  <li><strong>NIF/CIF:</strong> {nif}</li>
  <li><strong>Domicilio:</strong> {adreca}</li>
  <li><strong>Correo electrónico:</strong> <a href="mailto:{email}">{email}</a></li>
  <li><strong>Teléfono:</strong> {telefon}</li>
</ul>

<h2>Objeto</h2>
<p>Este sitio permite consultar el catálogo de {nom} y comprar productos, así como acceder
a sus noticias y actividades.</p>

<h2>Propiedad intelectual</h2>
<p>Los textos, imágenes, logotipos y el diseño de este sitio pertenecen a {nom} o a sus
autores y no pueden reproducirse sin autorización. Las carátulas y datos de los discos son
propiedad de sus respectivos titulares y se muestran únicamente para identificar los
productos a la venta.</p>

<h2>Responsabilidad</h2>
<p>Ponemos todo el esfuerzo en que la información sea correcta y esté actualizada, pero no
podemos garantizar que no haya errores puntuales de precio o de existencias. Si detectamos
un error antes de servir el pedido, te lo comunicaremos y podrás confirmarlo o cancelarlo
sin coste. Los enlaces a sitios de terceros son meramente informativos.</p>

<h2>Legislación aplicable</h2>
<p>Este sitio se rige por la legislación española. Si eres consumidor, cualquier conflicto
puede someterse a los juzgados y tribunales de tu domicilio.</p>
""".strip()),

    "privacitat": ("Política de privacidad", """
<p>Esta política explica cómo {nom} trata tus datos personales, de acuerdo con el Reglamento
(UE) 2016/679 (RGPD) y la Ley Orgánica 3/2018 (LOPDGDD).</p>

<h2>Responsable del tratamiento</h2>
<ul>
  <li><strong>Responsable:</strong> {nom} (NIF {nif})</li>
  <li><strong>Domicilio:</strong> {adreca}</li>
  <li><strong>Contacto para cuestiones de privacidad:</strong> <a href="mailto:{email}">{email}</a></li>
</ul>

<h2>Qué datos tratamos, para qué y con qué base legal</h2>
<table>
  <thead><tr><th>Finalidad</th><th>Datos</th><th>Base legal</th></tr></thead>
  <tbody>
    <tr><td>Crear y gestionar tu cuenta y tus sesiones</td>
        <td>Email, nombre, teléfono, contraseña (solo su <em>hash</em>) y, si entras con Google, tu email y nombre verificados por Google</td>
        <td>Ejecución del contrato (art. 6.1.b RGPD)</td></tr>
    <tr><td>Gestionar tus compras, peticiones de discos y, si te apuntas, el club del disco: cobro, envío, atención posventa y garantía</td>
        <td>Datos de contacto, dirección de entrega, pedidos, importes. No guardamos datos de tu tarjeta: los trata directamente la pasarela de pago.</td>
        <td>Ejecución del contrato (art. 6.1.b)</td></tr>
    <tr><td>Dejar constancia de que aceptaste las condiciones de venta antes de pagar, y de si ejerces el desistimiento</td>
        <td>Fecha y hora de la aceptación y, en su caso, del desistimiento, vinculadas al pedido</td>
        <td>Obligación legal e interés legítimo en acreditar el cumplimiento (art. 6.1.c y 6.1.f)</td></tr>
    <tr><td>Cumplir obligaciones fiscales, contables y mercantiles</td>
        <td>Pedidos, facturas y datos de facturación</td>
        <td>Obligación legal (art. 6.1.c)</td></tr>
    <tr><td>Enviarte la newsletter con novedades y actividades</td>
        <td>Email, nombre, idioma</td>
        <td>Consentimiento (art. 6.1.a). Puedes retirarlo en cualquier momento desde «Mi cuenta → Perfil» o con el enlace de baja de cada correo.</td></tr>
    <tr><td>Responder a las consultas que nos hagas</td>
        <td>Las que nos facilites</td>
        <td>Interés legítimo y/o medidas precontractuales (art. 6.1.f y 6.1.b)</td></tr>
    <tr><td>Seguridad del servicio y prevención del fraude y los abusos (límites de peticiones, registros técnicos)</td>
        <td>Dirección IP y datos técnicos de la conexión</td>
        <td>Interés legítimo (art. 6.1.f)</td></tr>
  </tbody>
</table>

<h2>Servicios de terceros que intervienen</h2>
<ul>
  <li><strong>Google (inicio de sesión).</strong> Si eliges entrar con Google, recibimos tu email y nombre,
      ya verificados. Google trata tus datos como responsable independiente, según su propia política.</li>
  <li><strong>Discogs.</strong> Si compras un disco a través de nuestro escaparate en Discogs, Discogs nos facilita tu nombre
      y dirección de entrega para poder enviártelo. Esos datos los tratamos para ejecutar esa compra.</li>
</ul>

<h2>Con quién compartimos los datos</h2>
<p>No vendemos ni cedemos tus datos con fines comerciales. Solo acceden a ellos proveedores que nos prestan
servicios y actúan como encargados del tratamiento bajo contrato:</p>
<ul>
  <li>Alojamiento e infraestructura técnica del sitio.</li>
  <li>Pasarela de pago con tarjeta (Redsys y la entidad financiera correspondiente).</li>
  <li>Servicio de envío de correo electrónico transaccional y de newsletter.</li>
  <li>Empresas de transporte, para que puedan entregarte el pedido.</li>
  <li>Nuestra gestoría, para la contabilidad y las obligaciones fiscales.</li>
</ul>
<p>También pueden recibir datos las administraciones públicas cuando una ley lo exija. Si algún proveedor trata datos
fuera del Espacio Económico Europeo, lo hace con garantías adecuadas
(cláusulas contractuales tipo de la Comisión Europea o decisión de adecuación).</p>

<h2>Cuánto tiempo los conservamos</h2>
<ul>
  <li><strong>Cuenta:</strong> mientras la mantengas. Si la eliminas, borramos los datos personales (perfil, direcciones, sesiones, vínculos).</li>
  <li><strong>Pedidos y facturas:</strong> el tiempo que exige la ley (mínimo 6 años, art. 30 del Código de Comercio, y el plazo de prescripción tributaria). Tras borrar la cuenta se conservan sin tu email.</li>
  <li><strong>Newsletter:</strong> hasta que te des de baja.</li>
  <li><strong>Consultas:</strong> el tiempo necesario para atenderlas y, después, durante los plazos de prescripción de posibles responsabilidades.</li>
</ul>

<h2>Tus derechos</h2>
<p>Puedes ejercer los derechos de acceso, rectificación, supresión, oposición, limitación del
tratamiento y portabilidad, y retirar el consentimiento que hayas dado:</p>
<ul>
  <li><strong>Desde tu cuenta:</strong> en «Mi cuenta → Perfil» puedes descargar todos tus datos y borrar tu cuenta tú mismo/a.</li>
  <li><strong>Por correo:</strong> escribiendo a <a href="mailto:{email}">{email}</a>. Responderemos en un máximo de un mes.</li>
</ul>
<p>Si consideras que no hemos tratado bien tus datos, puedes reclamar ante la
<a href="https://www.aepd.es" rel="noopener">Agencia Española de Protección de Datos</a>
o la <a href="https://apdcat.gencat.cat" rel="noopener">Autoridad Catalana de Protección de Datos</a>.</p>

<h2>Menores</h2>
<p>Este sitio no se dirige a menores de 14 años. Si eres menor de esa edad, no crees una cuenta
sin el consentimiento de tus padres o tutores.</p>
""".strip()),

    "cookies": ("Política de cookies", """
<p>Este sitio utiliza únicamente los almacenamientos <strong>estrictamente necesarios</strong> para
funcionar. No usamos cookies de analítica, publicidad ni seguimiento, y por eso no te mostramos un
banner de cookies. El contenido de terceros (vídeos, reproductores de música)
<strong>no se carga hasta que tú lo pides</strong>.</p>

<h2>Almacenamiento técnico (exento de consentimiento)</h2>
<table>
  <thead><tr><th>Nombre</th><th>Finalidad</th><th>Duración</th></tr></thead>
  <tbody>
    <tr><td><code>ulr_refresh</code> (cookie)</td><td>Mantener tu sesión iniciada de forma segura (httpOnly)</td><td>30 días o hasta que cierres sesión</td></tr>
    <tr><td><code>ulr_cart</code> (cookie)</td><td>Recordar tu carrito si no has iniciado sesión</td><td>30 días</td></tr>
    <tr><td><code>ulr_token</code> (almacenamiento local)</td><td>Credencial de acceso de corta duración de tu sesión</td><td>Hasta que cierres sesión</td></tr>
    <tr><td><code>ulr_lang</code> (almacenamiento local)</td><td>Recordar el idioma elegido</td><td>Persistente</td></tr>
    <tr><td><code>embed_consent_hosts</code> (almacenamiento local)</td><td>Recordar de qué proveedores has aceptado cargar contenido</td><td>Hasta que lo borres</td></tr>
    <tr><td><code>remena:…</code> (almacenamiento de sesión)</td><td>Conservar los resultados del catálogo mientras navegas, para volver sin perder el sitio</td><td>Hasta que cierres la pestaña</td></tr>
  </tbody>
</table>

<h2>Contenido de terceros (solo con tu clic)</h2>
<p>Algunas páginas pueden incluir reproductores de YouTube, Vimeo, Spotify, Mixcloud, Bandcamp o
SoundCloud. Hasta que pulses «Cargar contenido» no se conecta con esos servicios. Una vez cargado, el
tercero puede ver tu dirección IP e instalar sus propias cookies, bajo su política de privacidad. Si marcas
«Recordarme», lo guardamos en tu navegador; puedes borrarlo en cualquier momento con el enlace
«Borrar permisos de contenido de terceros» del pie de página.</p>

<h2>Cómo gestionar o eliminar cookies</h2>
<p>Puedes bloquear o borrar cookies desde la configuración de tu navegador. Si bloqueas las técnicas,
no podrás iniciar sesión ni usar el carrito.</p>

<p>Si añadiéramos en el futuro herramientas de analítica o publicidad que requieran consentimiento,
actualizaríamos esta política y te pediríamos permiso antes de activarlas.</p>

<p>Para cualquier duda, escríbenos a <a href="mailto:{email}">{email}</a>.</p>
""".strip()),

    "termes": ("Términos de uso", """
<p>El acceso y uso de este sitio, propiedad de {nom}, implica la aceptación de estos términos. Las compras se
rigen además por las <a href="/es/condicions-venda">condiciones de venta</a>.</p>

<h2>Uso del sitio</h2>
<p>Te comprometes a hacer un uso lícito del sitio y a no intentar acceder a áreas restringidas, alterar su
funcionamiento ni usarlo con fines fraudulentos.</p>

<h2>Cuenta de usuario</h2>
<p>Eres responsable de mantener confidenciales tus credenciales. Si sospechas que alguien ha accedido a tu cuenta,
avísanos en <a href="mailto:{email}">{email}</a>. Podemos suspender las cuentas que incumplan estos términos o la ley.</p>

<h2>Contenido y propiedad intelectual</h2>
<p>Consulta el <a href="/es/avis-legal">aviso legal</a>.</p>

<h2>Datos personales y cookies</h2>
<p>Consulta la <a href="/es/privacitat">política de privacidad</a> y la
<a href="/es/cookies">política de cookies</a>.</p>

<h2>Modificaciones</h2>
<p>Podemos actualizar estos términos; la versión vigente es siempre la publicada en esta página.</p>

<h2>Contacto</h2>
<p><a href="mailto:{email}">{email}</a></p>
""".strip()),

    "condicions-venda": ("Condiciones de venta", """
<p>Estas condiciones regulan las compras realizadas a través de este sitio a
<strong>{nom}</strong> (NIF {nif}, {adreca}; <a href="mailto:{email}">{email}</a>), de acuerdo con el
Real Decreto Legislativo 1/2007 (Ley General para la Defensa de los Consumidores y Usuarios). Al confirmar el
pedido marcando la casilla correspondiente declaras haberlas leído y aceptado.</p>

<h2>Productos</h2>
<p>Vendemos discos nuevos y de segunda mano. Los artículos de segunda mano son ejemplares únicos: indicamos el
estado del disco y de la funda (graduación) en la ficha, y la compra de un ejemplar lo agota. Las imágenes son
orientativas; para los ejemplares únicos prevalecen la descripción y el estado indicados.</p>

<h2>Precios e impuestos</h2>
<p>Todos los precios se expresan en euros. Los productos nuevos incluyen el IVA. Los artículos de segunda mano
pueden venderse bajo el régimen especial de bienes usados (REBU), en el que el IVA no se desglosa en la factura. Los
gastos de envío, si los hay, se indican y se suman al total antes de confirmar el pago.</p>

<h2>Proceso de compra y contrato</h2>
<p>Añades los productos al carrito, indicas tus datos y dirección y confirmas el pedido pulsando el botón
«Pedido con obligación de pago», lo que implica la obligación de pagar. Los ejemplares del carrito se reservan durante
unos minutos mientras completas el pago. Una vez pagado, recibirás un correo de confirmación. Podemos cancelar un pedido
y reembolsarte si un artículo no está realmente disponible. El contrato puede formalizarse en catalán, castellano o inglés.</p>

<h2>Pago</h2>
<p>El pago con tarjeta se procesa a través de la pasarela segura de Redsys. {nom} no tiene acceso ni guarda los
datos de tu tarjeta. También puede pagarse en tienda cuando hayas elegido recogida en tienda y esa opción esté disponible.</p>

<h2>Entrega</h2>
<p>Enviamos a la dirección que indiques o puedes recoger en tienda cuando esa opción esté disponible. Salvo que
se indique otro plazo, la entrega se realiza como máximo en 30 días desde la confirmación. Te avisaremos cuando el
pedido salga o esté preparado para recoger.</p>

<h2>Derecho de desistimiento (14 días)</h2>
<p>Tienes derecho a desistir de la compra, sin justificación, en un plazo de <strong>14 días naturales</strong>
desde que tú (o la persona que designes) recibes los productos. Puedes ejercerlo de forma sencilla con nuestra
<a href="/es/desistiment"><strong>función de desistimiento online</strong></a> (referencia del pedido y correo de compra),
o por correo electrónico a <a href="mailto:{email}">{email}</a>. Te enviaremos un correo que confirma que hemos
recibido tu comunicación. Debes devolver los productos en un máximo de 14 días desde la comunicación; el coste directo de
la devolución corre a tu cargo, salvo que se indique lo contrario. Te reembolsaremos todos los pagos, incluidos los
gastos de envío estándar, en un máximo de 14 días desde que recibamos tu comunicación, y podemos retener el reembolso
hasta recibir los productos o que demuestres su devolución. Responderás de la disminución de valor del bien
causada por una manipulación distinta de la necesaria para comprobar su naturaleza y funcionamiento.</p>
<p><strong>Excepciones:</strong> no hay derecho de desistimiento en las grabaciones sonoras precintadas que hayas
desprecintado tras la entrega, ni en bienes confeccionados conforme a tus especificaciones.</p>
<p><em>Modelo de formulario de desistimiento (a enviar a {email}):</em> «Por la presente os comunico que desisto del
contrato de venta de los siguientes productos: [productos]. Pedido n.º: [número]. Recibido el: [fecha]. Nombre: [nombre].
Dirección: [dirección]. Fecha: [fecha].»</p>

<h2>Garantía legal</h2>
<p>Los productos tienen la garantía legal de conformidad: <strong>3 años</strong> para los nuevos y
<strong>1 año</strong> para los de segunda mano, desde la entrega. Para los artículos de segunda mano, las partes
pactamos expresamente este plazo de 1 año, que aceptas al confirmar el pedido. Si el producto no es conforme, tienes
derecho a la reparación o sustitución y, si no es posible, a la rebaja del precio o a la resolución del contrato. Un ejemplar
de segunda mano no se considera no conforme por el desgaste propio del uso que ya conste en el estado indicado en la ficha.
Contáctanos en <a href="mailto:{email}">{email}</a> indicando el número de pedido.</p>

<h2>Reclamaciones</h2>
<p>Disponemos de hojas de reclamaciones en la tienda. También puedes dirigirte a la Agencia Catalana del Consumo
o a los mecanismos de resolución alternativa de conflictos de consumo. Para cualquier queja, escríbenos primero a
<a href="mailto:{email}">{email}</a>.</p>

<h2>Protección de datos</h2>
<p>Consulta la <a href="/es/privacitat">política de privacidad</a>.</p>
""".strip()),
}


EN_PAGES = {
    "avis-legal": ("Legal notice", """
<p>In compliance with Article 10 of Spanish Law 34/2002 on information society services and electronic
commerce (LSSI-CE), we inform you that this website is owned by:</p>

<ul>
  <li><strong>Owner:</strong> {nom}</li>
  <li><strong>Tax ID (NIF/CIF):</strong> {nif}</li>
  <li><strong>Address:</strong> {adreca}</li>
  <li><strong>Email:</strong> <a href="mailto:{email}">{email}</a></li>
  <li><strong>Phone:</strong> {telefon}</li>
</ul>

<h2>Purpose</h2>
<p>This website lets you browse the catalogue of {nom} and buy products, and read its news and events.</p>

<h2>Intellectual property</h2>
<p>The texts, images, logos and design of this website belong to {nom} or its authors and may not be
reproduced without permission. Album covers and record data belong to their respective owners and are shown
only to identify the products for sale.</p>

<h2>Liability</h2>
<p>We do our best to keep the information accurate and up to date, but we cannot guarantee there will be no
occasional errors in price or stock. If we find an error before fulfilling your order, we will tell you and you
may confirm or cancel it at no cost. Links to third-party sites are for information only.</p>

<h2>Governing law</h2>
<p>This website is governed by Spanish law. If you are a consumer, any dispute may be brought before the courts
of your place of residence.</p>
""".strip()),

    "privacitat": ("Privacy policy", """
<p>This policy explains how {nom} processes your personal data, in accordance with Regulation (EU) 2016/679
(GDPR) and Spanish Organic Law 3/2018 (LOPDGDD).</p>

<h2>Data controller</h2>
<ul>
  <li><strong>Controller:</strong> {nom} (Tax ID {nif})</li>
  <li><strong>Address:</strong> {adreca}</li>
  <li><strong>Privacy contact:</strong> <a href="mailto:{email}">{email}</a></li>
</ul>

<h2>What data we process, why, and on what legal basis</h2>
<table>
  <thead><tr><th>Purpose</th><th>Data</th><th>Legal basis</th></tr></thead>
  <tbody>
    <tr><td>Creating and managing your account and sessions</td>
        <td>Email, name, phone, password (only its hash) and, if you sign in with Google, your email and name as verified by Google</td>
        <td>Performance of a contract (Art. 6.1.b GDPR)</td></tr>
    <tr><td>Managing your purchases, record requests and, if you join, the record club: payment, shipping, after-sales and warranty</td>
        <td>Contact details, delivery address, orders, amounts. We do not store your card data: the payment gateway processes it directly.</td>
        <td>Performance of a contract (Art. 6.1.b)</td></tr>
    <tr><td>Keeping evidence that you accepted the terms of sale before paying, and of any withdrawal you exercise</td>
        <td>Date and time of acceptance and, where applicable, of withdrawal, linked to the order</td>
        <td>Legal obligation and legitimate interest in proving compliance (Art. 6.1.c and 6.1.f)</td></tr>
    <tr><td>Meeting tax, accounting and commercial obligations</td>
        <td>Orders, invoices and billing details</td>
        <td>Legal obligation (Art. 6.1.c)</td></tr>
    <tr><td>Sending you the newsletter with news and events</td>
        <td>Email, name, language</td>
        <td>Consent (Art. 6.1.a). You can withdraw it at any time from "My account → Profile" or with the unsubscribe link in each email.</td></tr>
    <tr><td>Answering your enquiries</td>
        <td>What you provide to us</td>
        <td>Legitimate interest and/or pre-contractual steps (Art. 6.1.f and 6.1.b)</td></tr>
    <tr><td>Service security and fraud and abuse prevention (rate limits, technical logs)</td>
        <td>IP address and technical connection data</td>
        <td>Legitimate interest (Art. 6.1.f)</td></tr>
  </tbody>
</table>

<h2>Third-party services involved</h2>
<ul>
  <li><strong>Google (sign-in).</strong> If you choose to sign in with Google, we receive your email and name, already
      verified. Google processes your data as an independent controller under its own policy.</li>
  <li><strong>Discogs.</strong> If you buy a record through our Discogs storefront, Discogs gives us your name and delivery
      address so we can ship it. We process that data to perform that purchase.</li>
</ul>

<h2>Who we share data with</h2>
<p>We do not sell or transfer your data for commercial purposes. Only service providers acting as data processors
under contract have access to it:</p>
<ul>
  <li>Hosting and technical infrastructure.</li>
  <li>Card payment gateway (Redsys and the relevant financial institution).</li>
  <li>Transactional email and newsletter delivery service.</li>
  <li>Carriers, so they can deliver your order.</li>
  <li>Our accountancy firm, for bookkeeping and tax obligations.</li>
</ul>
<p>Public authorities may also receive data when required by law. If a provider processes data outside the European
Economic Area, it does so with appropriate safeguards (European Commission
standard contractual clauses or an adequacy decision).</p>

<h2>How long we keep it</h2>
<ul>
  <li><strong>Account:</strong> while you keep it. If you delete it, we erase your personal data (profile, addresses, sessions, links).</li>
  <li><strong>Orders and invoices:</strong> as long as the law requires (at least 6 years, Art. 30 of the Spanish Commercial Code, plus the tax limitation period). After you delete your account they are kept without your email.</li>
  <li><strong>Newsletter:</strong> until you unsubscribe.</li>
  <li><strong>Enquiries:</strong> as long as needed to handle them and, afterwards, for the limitation periods of possible liabilities.</li>
</ul>

<h2>Your rights</h2>
<p>You can exercise your rights of access, rectification, erasure, objection, restriction and portability, and withdraw any
consent you have given:</p>
<ul>
  <li><strong>From your account:</strong> in "My account → Profile" you can download all your data and delete your account yourself.</li>
  <li><strong>By email:</strong> write to <a href="mailto:{email}">{email}</a>. We will reply within one month.</li>
</ul>
<p>If you believe we have not handled your data properly, you can complain to the
<a href="https://www.aepd.es" rel="noopener">Spanish Data Protection Agency</a> or the
<a href="https://apdcat.gencat.cat" rel="noopener">Catalan Data Protection Authority</a>.</p>

<h2>Minors</h2>
<p>This website is not aimed at children under 14. If you are under that age, do not create an account without the
consent of your parents or guardians.</p>
""".strip()),

    "cookies": ("Cookie policy", """
<p>This website only uses the storage that is <strong>strictly necessary</strong> for it to work. We do not use
analytics, advertising or tracking cookies, which is why we do not show a cookie banner. Third-party content (videos,
music players) <strong>is not loaded until you ask for it</strong>.</p>

<h2>Technical storage (exempt from consent)</h2>
<table>
  <thead><tr><th>Name</th><th>Purpose</th><th>Duration</th></tr></thead>
  <tbody>
    <tr><td><code>ulr_refresh</code> (cookie)</td><td>Keep you securely signed in (httpOnly)</td><td>30 days or until you sign out</td></tr>
    <tr><td><code>ulr_cart</code> (cookie)</td><td>Remember your cart if you are not signed in</td><td>30 days</td></tr>
    <tr><td><code>ulr_token</code> (local storage)</td><td>Short-lived access credential for your session</td><td>Until you sign out</td></tr>
    <tr><td><code>ulr_lang</code> (local storage)</td><td>Remember your chosen language</td><td>Persistent</td></tr>
    <tr><td><code>embed_consent_hosts</code> (local storage)</td><td>Remember which providers you agreed to load content from</td><td>Until you delete it</td></tr>
    <tr><td><code>remena:…</code> (session storage)</td><td>Keep catalogue results while you browse, so you can come back without losing your place</td><td>Until you close the tab</td></tr>
  </tbody>
</table>

<h2>Third-party content (only when you click)</h2>
<p>Some pages may include players from YouTube, Vimeo, Spotify, Mixcloud, Bandcamp or SoundCloud. Nothing connects to
those services until you press "Load content". Once loaded, the third party can see your IP address and set its own
cookies, under its own privacy policy. If you tick "Remember me" we store that in your browser; you can delete it at
any time with the "Clear third-party content permissions" link in the footer.</p>

<h2>How to manage or delete cookies</h2>
<p>You can block or delete cookies in your browser settings. If you block the technical ones, you will not be able to sign
in or use the cart.</p>

<p>If we add analytics or advertising tools that require consent in the future, we will update this policy and ask for
your permission before turning them on.</p>

<p>For any question, write to <a href="mailto:{email}">{email}</a>.</p>
""".strip()),

    "termes": ("Terms of use", """
<p>Accessing and using this website, owned by {nom}, means you accept these terms. Purchases are also governed by the
<a href="/en/condicions-venda">terms of sale</a>.</p>

<h2>Use of the website</h2>
<p>You agree to use the website lawfully and not to try to access restricted areas, interfere with its operation or use
it for fraudulent purposes.</p>

<h2>User account</h2>
<p>You are responsible for keeping your credentials confidential. If you suspect someone has accessed your account, tell
us at <a href="mailto:{email}">{email}</a>. We may suspend accounts that breach these terms or the law.</p>

<h2>Content and intellectual property</h2>
<p>See the <a href="/en/avis-legal">legal notice</a>.</p>

<h2>Personal data and cookies</h2>
<p>See the <a href="/en/privacitat">privacy policy</a> and the <a href="/en/cookies">cookie policy</a>.</p>

<h2>Changes</h2>
<p>We may update these terms; the version in force is always the one published on this page.</p>

<h2>Contact</h2>
<p><a href="mailto:{email}">{email}</a></p>
""".strip()),

    "condicions-venda": ("Terms of sale", """
<p>These terms govern purchases made through this website from <strong>{nom}</strong> (Tax ID {nif}, {adreca};
<a href="mailto:{email}">{email}</a>), in accordance with Spanish Royal Legislative Decree 1/2007 (General Law for the
Protection of Consumers and Users). By confirming your order and ticking the box you declare that you have read and
accepted them.</p>

<h2>Products</h2>
<p>We sell new and second-hand records. Second-hand items are unique copies: we state the condition of the record and the
sleeve (grading) on the product page, and buying a copy sells it out. Images are indicative; for unique copies, the
description and condition stated prevail.</p>

<h2>Prices and taxes</h2>
<p>All prices are in euros. New products include VAT. Second-hand items may be sold under the special scheme for used
goods (REBU), under which VAT is not itemised on the invoice. Shipping costs, if any, are shown and added to the total
before you confirm payment.</p>

<h2>Purchase process and contract</h2>
<p>You add products to the cart, enter your details and address, and confirm the order by pressing the "Order with
obligation to pay" button, which means you are obliged to pay. Items in your cart are reserved for a few minutes while
you complete payment. Once paid, you will receive a confirmation email. We may cancel an order and refund you if an item is
not actually available. The contract may be concluded in Catalan, Spanish or English.</p>

<h2>Payment</h2>
<p>Card payments are processed through the secure Redsys gateway. {nom} has no access to, and does not store, your card
details. You can also pay in store when you have chosen in-store pickup and that option is available.</p>

<h2>Delivery</h2>
<p>We ship to the address you provide, or you can collect in store when that option is available. Unless another period is
stated, delivery takes place within 30 days of confirmation. We will let you know when the order ships or is ready for
pickup.</p>

<h2>Right of withdrawal (14 days)</h2>
<p>You have the right to withdraw from the purchase, without giving any reason, within <strong>14 calendar days</strong>
of you (or a person you name) receiving the products. You can do so easily with our
<a href="/en/desistiment"><strong>online withdrawal function</strong></a> (order reference and purchase email), or by email
to <a href="mailto:{email}">{email}</a>. We will send you an email confirming we received your notice. You must return the
products within 14 days of notifying us; the direct cost of returning them is yours unless stated otherwise. We will refund
all payments, including standard delivery costs, within 14 days of receiving your notice, and may withhold the refund until
we receive the products or you show proof of return. You are liable for any loss in value of the goods resulting from
handling other than what is necessary to establish their nature and functioning.</p>
<p><strong>Exceptions:</strong> there is no right of withdrawal for sealed sound recordings that you have unsealed after
delivery, or for goods made to your specifications.</p>
<p><em>Model withdrawal form (send to {email}):</em> "I hereby give notice that I withdraw from my contract of sale of the
following products: [products]. Order no.: [number]. Received on: [date]. Name: [name]. Address: [address]. Date: [date]."</p>

<h2>Legal guarantee</h2>
<p>Products carry the legal guarantee of conformity: <strong>3 years</strong> for new items and <strong>1 year</strong> for
second-hand items, from delivery. For second-hand items, we expressly agree this 1-year period, which you accept when
confirming the order. If a product does not conform, you are entitled to repair or replacement and, if that is not possible,
to a price reduction or termination of the contract. A second-hand copy is not considered non-conforming because of
wear from use that is already reflected in the condition stated on the product page. Contact us at
<a href="mailto:{email}">{email}</a> quoting the order number.</p>

<h2>Complaints</h2>
<p>Complaint forms are available in the shop. You may also contact the Catalan Consumer Agency or alternative consumer
dispute-resolution bodies. For any complaint, please write to us first at <a href="mailto:{email}">{email}</a>.</p>

<h2>Data protection</h2>
<p>See the <a href="/en/privacitat">privacy policy</a>.</p>
""".strip()),
}
