<?php
/**
 * Chimera Localhost Manager - Web Interface
 * Mantiene el estilo visual de Chimera Panel V-0.8
 */
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
                        
                        // Intentar detectar si el index está en una subcarpeta (ej. frameworks)
                        $target_url = $folder;
                        if (!file_exists($folder . "/index.php") && !file_exists($folder . "/index.html")) {
                            $sub_folders = array_filter(glob($folder . '/*'), 'is_dir');
                            foreach ($sub_folders as $sub) {
                                if (file_exists($sub . "/index.php") || file_exists($sub . "/index.html")) {
                                    $target_url = $sub;
                                    break;
                                }
                            }
                        }
                    ?>
                    <a href="/<?php echo $target_url; ?>" class="project-card">
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