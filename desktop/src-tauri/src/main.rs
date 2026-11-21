#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::{TcpListener, TcpStream};
use std::sync::Mutex;
use std::time::Duration;

use tauri::{Manager, RunEvent, WebviewUrl, WebviewWindowBuilder, WindowEvent};
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;

/// Porta preferida do servidor local. Manter a mesma porta entre execuções
/// preserva o `localStorage` da interface (último projeto e última análise).
const PORTA_BASE: u16 = 47823;

/// Servidor Python empacotado como sidecar. Fica vivo enquanto o app estiver aberto.
struct Servidor(Mutex<Option<CommandChild>>);

fn porta_disponivel(porta: u16) -> bool {
    TcpListener::bind(("127.0.0.1", porta)).is_ok()
}

/// Primeira porta livre a partir de `PORTA_BASE`. O `redes web` também desloca
/// a porta se ela estiver ocupada, mas escolhemos antes para saber o endereço.
fn escolhe_porta() -> u16 {
    (PORTA_BASE..PORTA_BASE + 12)
        .find(|porta| porta_disponivel(*porta))
        .unwrap_or(PORTA_BASE)
}

fn servidor_responde(porta: u16) -> bool {
    let endereco = match format!("127.0.0.1:{porta}").parse() {
        Ok(endereco) => endereco,
        Err(_) => return false,
    };
    TcpStream::connect_timeout(&endereco, Duration::from_millis(400)).is_ok()
}

fn main() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let porta = escolhe_porta();
            let (mut eventos, filho) = app
                .shell()
                .sidecar("redes-servidor")?
                .args(["--porta", &porta.to_string(), "--nao-abrir"])
                .env("REDES_PAI_PID", std::process::id().to_string())
                .spawn()?;
            app.manage(Servidor(Mutex::new(Some(filho))));

            // Consome a saída do sidecar; sem isso o cano enche e o servidor trava.
            tauri::async_runtime::spawn(async move {
                while eventos.recv().await.is_some() {}
            });

            let handle = app.handle().clone();
            std::thread::spawn(move || {
                let mut pronto = false;
                for _ in 0..300 {
                    if servidor_responde(porta) {
                        pronto = true;
                        break;
                    }
                    std::thread::sleep(Duration::from_millis(200));
                }
                let url = format!("http://127.0.0.1:{porta}/");
                if pronto {
                    if let Some(janela) = handle.get_webview_window("main") {
                        let _ = janela.navigate(url.parse().expect("endereço local"));
                    } else {
                        let _ = WebviewWindowBuilder::new(
                            &handle,
                            "main",
                            WebviewUrl::External(url.parse().expect("endereço local")),
                        )
                        .title("Redes")
                        .inner_size(1280.0, 800.0)
                        .build();
                    }
                } else if let Some(janela) = handle.get_webview_window("main") {
                    let _ = janela.eval(
                        "document.getElementById('status').hidden = true; \
                         document.getElementById('erro').hidden = false;",
                    );
                }
            });
            Ok(())
        })
        .on_window_event(|janela, evento| {
            // Fechar a janela encerra o servidor mesmo se o app seguir no Dock.
            if let WindowEvent::Destroyed = evento {
                encerra_servidor(janela.app_handle());
            }
        })
        .build(tauri::generate_context!())
        .expect("erro ao montar o aplicativo Redes");

    app.run(|handle, evento| {
        if let RunEvent::Exit = evento {
            encerra_servidor(handle);
        }
    });
}

fn encerra_servidor<R: tauri::Runtime>(handle: &tauri::AppHandle<R>) {
    if let Some(estado) = handle.try_state::<Servidor>() {
        if let Some(filho) = estado.0.lock().ok().and_then(|mut guarda| guarda.take()) {
            let _ = filho.kill();
        }
    }
}
