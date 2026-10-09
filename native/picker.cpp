// SPDX-License-Identifier: MIT
// Thin process adapter for KDE's maintained file widget. No custom file browser.
#include <QApplication>
#include <QDialog>
#include <QDialogButtonBox>
#include <QDir>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QPalette>
#include <QPushButton>
#include <QSocketNotifier>
#include <QStandardPaths>
#include <QStyleFactory>
#include <QTemporaryDir>
#include <QTimer>
#include <QVBoxLayout>
#include <QWindow>
#include <KDirOperator>
#include <KFileWidget>
#include <KIconLoader>
#include <csignal>
#include <cstdio>
#include <sys/prctl.h>
#include <unistd.h>

static volatile sig_atomic_t cancelled = 0;
static void stop(int) { cancelled = 1; }
static void output(const QJsonObject &value) {
    const auto bytes = QJsonDocument(value).toJson(QJsonDocument::Compact);
    fwrite(bytes.constData(), 1, bytes.size(), stdout);
    fputc('\n', stdout);
    fflush(stdout);
}

int runPicker(int argc, char **argv, void (*testReady)(KFileWidget *, QDialog *) = nullptr) {
    // KFileWidget normally saves recent paths and view preferences. Isolate
    // those writes; never modify kdeglobals, Dolphin, or portal configuration.
    const auto runtime = qEnvironmentVariable("XDG_RUNTIME_DIR", QDir::tempPath());
    QTemporaryDir local(runtime + "/dms-airdrop-picker-XXXXXX");
    if (!local.isValid()) return 2;
    for (const auto *name : {"XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"}) {
        auto path = local.path() + '/' + name;
        QDir().mkpath(path);
        qputenv(name, path.toUtf8());
    }
    // A missing 'kde' platform theme otherwise falls back anyway. Restrict this
    // process to its own Qt Widgets dialog; no portal or global theme override.
    qputenv("QT_QPA_PLATFORMTHEME", "");
    std::signal(SIGTERM, stop);
    std::signal(SIGINT, stop);
    const auto parent = getppid();
    prctl(PR_SET_PDEATHSIG, SIGTERM);
    if (getppid() != parent) return 1;
    QApplication app(argc, argv);
    if (argc == 2 && QByteArray(argv[1]) == "--check") {
        output({{QStringLiteral("ok"), true}});
        return 0;
    }
    app.setApplicationName("dms-airdrop-picker");
    app.setDesktopFileName("dmsAirDrop");
    if (auto *style = QStyleFactory::create("breeze")) app.setStyle(style);
    QIcon::setThemeName("breeze");
    // DMS supplies its actual palette as one JSON argument, with no shell.
    QJsonObject options;
    if (argc > 1) options = QJsonDocument::fromJson(argv[1]).object();
    const auto colors = options.value("palette").toObject();
    auto palette = app.palette();
    for (const auto &entry : {std::pair{QPalette::Window, "surface"},
                             {QPalette::Base, "base"}, {QPalette::AlternateBase, "surface"},
                             {QPalette::Button, "surface"}, {QPalette::WindowText, "text"},
                             {QPalette::Text, "text"}, {QPalette::ButtonText, "text"},
                             {QPalette::Highlight, "primary"}, {QPalette::HighlightedText, "onPrimary"}}) {
        const QColor color(colors.value(entry.second).toString());
        if (color.isValid()) palette.setColor(entry.first, color);
    }
    app.setPalette(palette);
    QIcon::setThemeName(palette.color(QPalette::Window).lightnessF() < 0.5 ? "breeze-dark" : "breeze");
    KIconLoader::global()->setCustomPalette(palette);
    QDialog dialog;
    dialog.setWindowTitle("Send with AirDrop");
    dialog.resize(960, 700);
    auto *layout = new QVBoxLayout(&dialog);
    QString folder = options.value("folder").toString();
    if (!QFileInfo(folder).isDir()) folder = QStandardPaths::writableLocation(QStandardPaths::PicturesLocation);
    if (!QFileInfo(folder).isDir()) folder = QDir::homePath();
    auto *picker = new KFileWidget(QUrl::fromLocalFile(folder), &dialog);
    picker->setOperationMode(KFileWidget::Opening);
    picker->setMode(KFile::Files | KFile::ExistingOnly | KFile::LocalOnly);
    picker->setSupportedSchemes({QStringLiteral("file")});
    picker->setViewMode(KFile::Simple);
    picker->setInlinePreviewShown(true);
    picker->dirOperator()->setIconSize(96);
    layout->addWidget(picker);
    auto *buttons = new QDialogButtonBox(&dialog);
    buttons->addButton(picker->okButton(), QDialogButtonBox::AcceptRole);
    buttons->addButton(picker->cancelButton(), QDialogButtonBox::RejectRole);
    picker->okButton()->setText("Choose files");
    layout->addWidget(buttons);
    QObject::connect(buttons, &QDialogButtonBox::accepted, picker, &KFileWidget::slotOk);
    QObject::connect(buttons, &QDialogButtonBox::rejected, &dialog, &QDialog::reject);
    QObject::connect(picker, &KFileWidget::accepted, &dialog, [&] {
        picker->accept();
        dialog.accept();
    });
    // Parent-owned stdin is also a lifeline. Its EOF cancels an orphan chooser.
    QSocketNotifier input(STDIN_FILENO, QSocketNotifier::Read);
    QByteArray pending;
    QObject::connect(&input, &QSocketNotifier::activated, &dialog, [&] {
        char buffer[128];
        const auto size = read(STDIN_FILENO, buffer, sizeof buffer);
        if (size <= 0) { input.setEnabled(false); dialog.reject(); return; }
        pending.append(buffer, size);
        while (pending.contains('\n')) {
            const auto line = pending.left(pending.indexOf('\n'));
            pending.remove(0, line.size() + 1);
            if (line == "focus") { dialog.showNormal(); dialog.raise(); dialog.activateWindow(); }
            else if (line == "cancel") dialog.reject();
        }
        if (pending.size() > 1024) pending.clear();
    });
    QTimer signalCheck;
    QObject::connect(&signalCheck, &QTimer::timeout, &dialog, [&] { if (cancelled) dialog.reject(); });
    signalCheck.start(100);
    dialog.show();
    if (testReady) testReady(picker, &dialog);
    QTimer::singleShot(0, &dialog, [&] { output({{"event", "opened"}}); });
    const int result = dialog.exec();
    QJsonArray urls;
    if (result == QDialog::Accepted) {
        for (const auto &url : picker->selectedUrls()) {
            if (!url.isLocalFile() || !QFileInfo(url.toLocalFile()).isFile()) return 2;
            urls.append(url.toString(QUrl::FullyEncoded));
        }
        if (urls.isEmpty() || urls.size() > 256) return 2;
    }
    output({{"event", "result"}, {"accepted", result == QDialog::Accepted}, {"urls", urls}});
    return 0;
}

#ifndef DMS_PICKER_LIBRARY
int main(int argc, char **argv) { return runPicker(argc, argv); }
#endif
