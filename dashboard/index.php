<?php
/**
 * Chimera Localhost Manager - Web Interface
 * Mantiene el estilo visual de Chimera Panel V-0.8
 */
$dir = ".";
$exclude = array('.', '..', 'css', 'img', 'js', 'iconos');
$folders = array_filter(glob('*'), 'is_dir');

$php_version = phpversion();
$server_soft = $_SERVER['SERVER_SOFTWARE'];
?>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chimera Localhost - Panel</title>
    <link rel="stylesheet" href="diseno.css">
</head>
<body>
    <div class="container">
        <header>
            <div class="logo-area">
                <h1>CHIMERA PANEL <span>WEB</span></h1>
                <p class="status-bar">
                    <span class="pill">🐘 PHP <?php echo $php_version; ?></span>
                    <span class="pill">🌐 <?php echo $server_soft; ?></span>
                    <a href="/phpmyadmin" class="pill admin-btn">🗄️ phpMyAdmin</a>
                </p>
            </div>
        </header>

        <main>
            <h2 class="section-title">📂 Proyectos Disponibles</h2>
            <div class="project-grid">
                <?php foreach ($folders as $folder): if (in_array($folder, $exclude)) continue; ?>
                    <?php 
                        $icon_path = "iconos/" . $folder . ".png";
                        $has_icon = file_exists($icon_path);

                        // Verificamos si la carpeta tiene archivos de inicio
                        $is_empty = !file_exists($folder . "/index.php") && !file_exists($folder . "/index.html");
                    ?>
                    <a href="<?php echo $is_empty ? '#' : '/' . $folder; ?>" 
                       class="project-card <?php echo $is_empty ? 'empty' : ''; ?>"
                       <?php if ($is_empty) echo 'onclick="alert(\'La carpeta ['.$folder.'] está vacía.\n\nNo contiene un archivo index.php o index.html.\'); return false;"'; ?>>
                        <div class="icon">
                            <?php echo $has_icon ? "<img src='$icon_path' class='project-icon'>" : "📁"; ?>
                        </div>
                        <div class="info">
                            <span class="name"><?php echo $folder; ?></span>
                            <span class="url">localhost/<?php echo $folder; ?></span>
                        </div>
                    </a>
                <?php endforeach; ?>
            </div>
        </main>
    </div>
</body>
</html>