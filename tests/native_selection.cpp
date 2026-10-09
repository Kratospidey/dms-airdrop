// Test-only driver. The production picker has no automatic-accept path.
#include <QApplication>
#include <QDialog>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTimer>
#include <KFileWidget>
int runPicker(int, char **, void (*)(KFileWidget *, QDialog *));
static QList<QUrl> chosen;
int main(int argc, char **argv) {
    const auto options = QJsonDocument::fromJson(argv[1]).object();
    for (const auto &value : options.value("test_urls").toArray()) chosen.append(QUrl(value.toString()));
    return runPicker(argc, argv, [](KFileWidget *picker, QDialog *dialog) {
        QTimer::singleShot(600, dialog, [picker] { picker->setSelectedUrls(chosen); picker->slotOk(); });
        QTimer::singleShot(8000, dialog, &QDialog::reject);
    });
}
