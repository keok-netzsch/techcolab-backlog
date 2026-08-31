# Evening push - Second Brain vault system
# Scoped to Kelvin only for now - add team members here once each one has
# passed onboarding validation (validate-vault-setup.ps1) and signed the
# checklist. See PO-12 - Second Brain/Manual.md, Governance section.
#
# Switched from toast to a blocking MessageBox 2026-08-11: the toast API
# reported success every time (confirmed via the Windows notification
# registry - 10 real entries logged, timestamps matching every scheduled
# fire) but Kelvin never saw a visible banner - likely Focus Assist
# suppressing the popup while still logging it. A MessageBox is not subject
# to Focus Assist and stays on screen (TopMost) until manually dismissed,
# so there is no way to silently miss it.

Add-Type -AssemblyName System.Windows.Forms

$title = "Second Brain - hora de graduar"
$message = "Revise as notas de hoje. Algo pronto para o vault central? Peca ao seu Claude para checar as regras e copiar."

try {
    $form = New-Object System.Windows.Forms.Form
    $form.TopMost = $true
    $form.Opacity = 0
    $form.ShowInTaskbar = $false
    $form.StartPosition = "CenterScreen"
    $form.Size = New-Object System.Drawing.Size(0, 0)
    $form.Show()
    [System.Windows.Forms.MessageBox]::Show($form, $message, $title, [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Information) | Out-Null
    $form.Close()
    Write-Host "MessageBox shown and dismissed: $title"
} catch {
    Write-Host "MessageBox failed: $($_.Exception.Message)"
    exit 1
}
