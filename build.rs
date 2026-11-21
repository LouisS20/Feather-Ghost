// Intègre l'icône dans FeatherGhost.exe (Windows uniquement).
fn main() {
    #[cfg(windows)]
    {
        let mut res = winresource::WindowsResource::new();
        res.set_icon("assets/icon.ico");
        res.set("ProductName", "Feather Ghost");
        res.set("FileDescription", "Feather Ghost");
        let _ = res.compile();
    }
}
