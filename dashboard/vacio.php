<?php
/**
 * Chimera Localhost Manager - Página de Carpeta Vacía
 */
$request_uri = $_SERVER['REQUEST_URI'];
$clean_uri = parse_url($request_uri, PHP_URL_PATH);
// Obtenemos la ruta física real combinando la raíz del servidor con la URI solicitada
$physical_path = realpath($_SERVER['DOCUMENT_ROOT'] . DIRECTORY_SEPARATOR . ltrim($clean_uri, '/'));

$items = [];
if ($physical_path && is_dir($physical_path)) {
    $dir_content = @scandir($physical_path);
    if ($dir_content) {
        // Excluimos archivos internos del panel y ocultos
        $exclude = array('.', '..', 'css', 'img', 'js', 'iconos', 'vacio.php', 'diseno.css', 'index.php', 'fondo.png', 'logo.png', 'teto.png');
        $items = array_diff($dir_content, $exclude);
        natcasesort($items); // Orden natural (A, B, C...)
    }
}
?>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Carpeta Vacía - Chimera Panel</title>
    <link rel="stylesheet" href="/diseno.css">
    <style>
        .message-box { text-align: center; padding: 20px; }
        .actions { margin-top: 30px; display: flex; justify-content: center; gap: 15px; }
        .icon-big { font-size: 4rem; margin-bottom: 10px; display: block; }
        .explorer { margin: 20px auto; max-width: 600px; display: flex; flex-direction: column; gap: 5px; text-align: left; }
        .item-row { background: rgba(255,255,255,0.05); padding: 12px 20px; border-radius: 8px; text-decoration: none; color: #eee; display: flex; align-items: center; gap: 10px; transition: background 0.2s; }
        .item-row:hover { background: rgba(255,255,255,0.15); border-color: #ec1616; }
        .item-row.folder { border-left: 3px solid #ec1616; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>CHIMERA PANEL <span>AVISO</span></h1>
        </header>
        <main class="message-box">
            <span class="icon-big">📂</span>
            <h2 class="section-title">Esta carpeta está vacía</h2>
            <p>No se encontró un archivo de índice en <code><?php echo htmlspecialchars($clean_uri); ?></code></p>

            <?php if (!empty($items)): ?>
                <div class="explorer">
                    <p style="opacity: 0.6; font-size: 0.9rem; margin-bottom: 10px;">Contenido disponible en este directorio:</p>
                    <?php foreach ($items as $item): 
                        $item_path = $physical_path . DIRECTORY_SEPARATOR . $item;
                        $is_folder = is_dir($item_path);
                        $link = rtrim($clean_uri, '/') . '/' . $item;
                    ?>
                        <a href="<?php echo $link; ?>" class="item-row <?php echo $is_folder ? 'folder' : ''; ?>">
                            <span><?php echo $is_folder ? "📁" : "📄"; ?></span>
                            <span><?php echo $item; ?></span>
                        </a>
                    <?php endforeach; ?>
                </div>
            <?php endif; ?>

            <div class="actions">
                <a href="javascript:history.back()" class="pill admin-btn" style="text-decoration: none; padding: 10px 20px;">⬅️ Regresar Atrás</a>
                <a href="/" class="pill admin-btn" style="text-decoration: none; padding: 10px 20px;">🏠 Ir al Panel</a>
            </div>
        </main>
    </div>
</body>
</html>