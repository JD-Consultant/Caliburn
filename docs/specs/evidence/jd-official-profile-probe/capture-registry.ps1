$ErrorActionPreference = 'Stop'
$f02Inv = Get-Content license-inventory.json -Raw | ConvertFrom-Json
$f02Names = @('platejs','@platejs/core','@platejs/basic-nodes','@platejs/list-classic','@platejs/table','@platejs/diff','@platejs/resizable','react','react-dom')
$f02Targets = $f02Inv.packages | Where-Object { $f02Names -contains $_.name -or $_.licenses.Count -eq 0 }
$f02Metadata = @()
$f02LicenseSources = @()
New-Item -ItemType Directory -Force -Path sources/registry,licenses/official-fallback | Out-Null
foreach ($f02Target in $f02Targets) {
  $f02Meta = Invoke-RestMethod -Uri ('https://registry.npmjs.org/' + $f02Target.name + '/' + $f02Target.version)
  $f02Safe = $f02Target.name.Replace('/','__')
  $f02Meta | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath ('sources/registry/' + $f02Safe + '.json') -Encoding utf8
  $f02Metadata += [pscustomobject]@{name=$f02Meta.name;version=$f02Meta.version;license=$f02Meta.license;gitHead=$f02Meta.gitHead;url=('https://registry.npmjs.org/' + $f02Target.name + '/' + $f02Target.version)}
  if ($f02Target.licenses.Count -eq 0) {
    $f02Repo = if ($f02Meta.repository -is [string]) { $f02Meta.repository } else { $f02Meta.repository.url }
    $f02Repo = $f02Repo -replace '^git\+','' -replace '^git://','https://' -replace '\.git$',''
    $f02RawRepo = $f02Repo -replace '^https://github.com/','https://raw.githubusercontent.com/'
    $f02Found = $false
    if ($f02Meta.gitHead -and $f02RawRepo -match '^https://raw.githubusercontent.com/') {
      foreach ($f02LicenseName in @('LICENSE','LICENSE.md','License.md')) {
        $f02URL = $f02RawRepo + '/' + $f02Meta.gitHead + '/' + $f02LicenseName
        try {
          $f02License = Invoke-WebRequest -UseBasicParsing -Uri $f02URL
          $f02Relative = 'licenses/official-fallback/' + $f02Safe + '-' + $f02LicenseName
          [IO.File]::WriteAllText((Join-Path (Get-Location) $f02Relative),[string]$f02License.Content)
          $f02LicenseSources += [pscustomobject]@{name=$f02Target.name;version=$f02Target.version;url=$f02URL;path=$f02Relative;installedLicenseAbsent=$true}
          $f02Found=$true
          break
        } catch {}
      }
    }
    if (-not $f02Found) { $f02LicenseSources += [pscustomobject]@{name=$f02Target.name;version=$f02Target.version;installedLicenseAbsent=$true;note='Exact metadata declares MIT; fixed gitHead root LICENSE unavailable in bounded filename checks.'} }
  }
}
[pscustomobject]@{checkedOn='2026-09-10';packages=$f02Metadata} | ConvertTo-Json -Depth 8 | Set-Content sources/registry-metadata.json -Encoding utf8
[pscustomobject]@{checkedOn='2026-09-10';sources=$f02LicenseSources} | ConvertTo-Json -Depth 8 | Set-Content licenses/official-fallback-sources.json -Encoding utf8
$f02LicenseSources | Select-Object name,version,path,note | ConvertTo-Json -Depth 3
