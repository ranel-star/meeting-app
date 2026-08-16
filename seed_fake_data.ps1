param(
  [string]$DatabasePath = (Join-Path $PSScriptRoot 'db\meeting_app.sqlite3'),
  [string]$UploadsPath = (Join-Path $PSScriptRoot 'instance\uploads'),
  [int]$TargetUserCount = 60,
  [int]$RandomSeed = 20260807,
  [string]$DemoPassword = 'Password123!'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Find-SqliteDll {
  $knownPaths = @(
    'C:\Program Files\ASUS\ARMOURY CRATE Service\ThrottlePlugin\System.Data.SQLite.dll',
    'C:\Program Files (x86)\System.Data.SQLite\bin\System.Data.SQLite.dll',
    'C:\Program Files\System.Data.SQLite\bin\System.Data.SQLite.dll'
  )

  foreach ($path in $knownPaths) {
    if (Test-Path -LiteralPath $path) {
      return $path
    }
  }

  $searchRoots = @('C:\Program Files', 'C:\Program Files (x86)')
  foreach ($root in $searchRoots) {
    $match = Get-ChildItem -Path $root -Recurse -Filter System.Data.SQLite.dll -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -ne $match) {
      return $match.FullName
    }
  }

  throw 'Could not find System.Data.SQLite.dll on this machine.'
}

function Convert-DbValue {
  param([object]$Value)
  if ($null -eq $Value) {
    return [DBNull]::Value
  }
  return $Value
}

function Invoke-SqliteNonQuery {
  param(
    [System.Data.SQLite.SQLiteConnection]$Connection,
    [System.Data.SQLite.SQLiteTransaction]$Transaction,
    [string]$Sql,
    [hashtable]$Parameters = @{}
  )

  $command = $Connection.CreateCommand()
  $command.Transaction = $Transaction
  $command.CommandText = $Sql
  foreach ($key in $Parameters.Keys) {
    $null = $command.Parameters.AddWithValue("@$key", (Convert-DbValue $Parameters[$key]))
  }
  $null = $command.ExecuteNonQuery()
}

function Invoke-SqliteScalar {
  param(
    [System.Data.SQLite.SQLiteConnection]$Connection,
    [System.Data.SQLite.SQLiteTransaction]$Transaction,
    [string]$Sql,
    [hashtable]$Parameters = @{}
  )

  $command = $Connection.CreateCommand()
  $command.Transaction = $Transaction
  $command.CommandText = $Sql
  foreach ($key in $Parameters.Keys) {
    $null = $command.Parameters.AddWithValue("@$key", (Convert-DbValue $Parameters[$key]))
  }
  return $command.ExecuteScalar()
}

function New-RandomSalt {
  param(
    [System.Random]$Rng,
    [int]$Length = 16
  )

  $chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'.ToCharArray()
  $builder = New-Object System.Text.StringBuilder
  for ($i = 0; $i -lt $Length; $i++) {
    $null = $builder.Append($chars[$Rng.Next(0, $chars.Length)])
  }
  return $builder.ToString()
}

function New-WerkzeugPasswordHash {
  param(
    [string]$Password,
    [System.Random]$Rng,
    [int]$Iterations = 260000
  )

  $salt = New-RandomSalt -Rng $Rng -Length 16
  $saltBytes = [System.Text.Encoding]::UTF8.GetBytes($salt)
  $derive = [System.Security.Cryptography.Rfc2898DeriveBytes]::new(
    $Password,
    $saltBytes,
    $Iterations,
    [System.Security.Cryptography.HashAlgorithmName]::SHA256
  )
  $hashBytes = $derive.GetBytes(32)
  $hashHex = ([System.BitConverter]::ToString($hashBytes)).Replace('-', '').ToLowerInvariant()
  return "pbkdf2:sha256:$Iterations`$$salt`$$hashHex"
}

function New-BirthDate {
  param(
    [System.Random]$Rng,
    [int]$MinAge = 21,
    [int]$MaxAge = 44
  )

  $today = Get-Date
  $age = $Rng.Next($MinAge, $MaxAge + 1)
  $year = $today.Year - $age
  $month = $Rng.Next(1, 13)
  $day = $Rng.Next(1, [DateTime]::DaysInMonth($year, $month) + 1)
  return (Get-Date -Year $year -Month $month -Day $day).ToString('yyyy-MM-dd')
}

function Get-Age {
  param([string]$BirthDateText)
  try {
    $birthDate = [DateTime]::ParseExact($BirthDateText, 'yyyy-MM-dd', $null)
  } catch {
    return $null
  }

  $today = Get-Date
  $age = $today.Year - $birthDate.Year
  if (($today.Month -lt $birthDate.Month) -or (($today.Month -eq $birthDate.Month) -and ($today.Day -lt $birthDate.Day))) {
    $age--
  }
  return $age
}

function PreferenceAllowsGender {
  param(
    [string]$Preference,
    [string]$Gender
  )

  if ([string]::IsNullOrWhiteSpace($Preference) -or $Preference -in @('Everyone', 'Prefer not to say')) {
    return $true
  }
  if ([string]::IsNullOrWhiteSpace($Gender)) {
    return $false
  }

  switch ($Preference) {
    'Women' { return $Gender -eq 'Woman' }
    'Men' { return $Gender -eq 'Man' }
    'Non-binary' { return $Gender -eq 'Non-binary' }
    default { return $true }
  }
}

function Get-MatchScore {
  param(
    [hashtable]$UserA,
    [hashtable]$UserB
  )

  $score = 0
  $ageA = Get-Age $UserA['birth_date']
  $ageB = Get-Age $UserB['birth_date']

  if (PreferenceAllowsGender -Preference $UserA['gender_preference'] -Gender $UserB['gender']) { $score += 25 }
  if (PreferenceAllowsGender -Preference $UserB['gender_preference'] -Gender $UserA['gender']) { $score += 25 }
  if ($null -ne $ageB -and $UserA['min_age'] -le $ageB -and $ageB -le $UserA['max_age']) { $score += 25 }
  if ($null -ne $ageA -and $UserB['min_age'] -le $ageA -and $ageA -le $UserB['max_age']) { $score += 25 }

  return $score
}

function New-ProfileBio {
  param(
    [System.Random]$Rng,
    [string]$Name
  )

  $openers = @(
    'Enjoys coffee runs, live music, and weekend markets.',
    'Likes good food, long walks, and trying new places.',
    'Reads a lot, laughs easily, and never says no to dessert.',
    'Into design, travel, and finding the best ramen in town.',
    'A calm person with a playful streak and a packed playlist.',
    'Usually between a workout class, a book, and a last-minute plan.',
    'Loves clean data, strong opinions about pizza, and good sunsets.',
    'Curious, friendly, and always planning the next little adventure.'
  )

  $hobbies = @(
    'spending Sundays in museums',
    'trying new espresso bars',
    'bouldering and spontaneous hikes',
    'cooking for friends',
    'watching indie films',
    'taking late-night walks',
    'planning trips with way too many tabs open',
    'hunting for vinyl records'
  )

  $traits = @(
    'values honest conversations',
    'appreciates a good sense of humor',
    'likes low-pressure first dates',
    'is happiest when learning something new',
    'keeps a tidy calendar and an open mind',
    'enjoys slow mornings and strong coffee',
    'likes thoughtful questions',
    'prefers cozy nights over crowded parties'
  )

  return "$($openers[$Rng.Next(0, $openers.Count)]) $Name also enjoys $($hobbies[$Rng.Next(0, $hobbies.Count)]) and $($traits[$Rng.Next(0, $traits.Count)])."
}

function New-ProfileCity {
  param([System.Random]$Rng)
  $cities = @(
    'Tel Aviv', 'Jerusalem', 'Haifa', 'Ramat Gan', 'Givatayim', 'Herzliya', 'Netanya',
    'Rishon LeZion', 'Petah Tikva', 'Rehovot', 'Modiin', 'Kfar Saba', 'Ashdod', 'Beer Sheva',
    'Raanana', 'Bat Yam', 'Holon', 'Nahariya', 'Eilat', 'Tiberias'
  )
  return $cities[$Rng.Next(0, $cities.Count)]
}

function New-Gender {
  param([System.Random]$Rng)
  $weighted = @('Woman', 'Woman', 'Woman', 'Man', 'Man', 'Man', 'Non-binary', 'Prefer not to say')
  return $weighted[$Rng.Next(0, $weighted.Count)]
}

function New-Preference {
  param(
    [System.Random]$Rng,
    [string]$Gender
  )

  switch ($Gender) {
    'Woman' { $options = @('Men', 'Men', 'Women', 'Everyone', 'Prefer not to say') }
    'Man' { $options = @('Women', 'Women', 'Men', 'Everyone', 'Prefer not to say') }
    'Non-binary' { $options = @('Everyone', 'Everyone', 'Women', 'Men', 'Prefer not to say') }
    default { $options = @('Everyone', 'Everyone', 'Women', 'Men', 'Prefer not to say') }
  }

  return $options[$Rng.Next(0, $options.Count)]
}

function New-RandomTimestamp {
  param(
    [System.Random]$Rng,
    [datetime]$Start,
    [datetime]$End
  )

  $span = $End - $Start
  $offsetSeconds = $Rng.Next(0, [int]$span.TotalSeconds + 1)
  return $Start.AddSeconds($offsetSeconds).ToString('yyyy-MM-dd HH:mm:ss')
}

function Add-PhotoForUser {
  param(
    [System.Data.SQLite.SQLiteConnection]$Connection,
    [System.Data.SQLite.SQLiteTransaction]$Transaction,
    [System.Random]$Rng,
    [int]$UserId,
    [System.IO.FileInfo[]]$BasePhotos,
    [string]$UploadsPath
  )

  $source = $BasePhotos[$Rng.Next(0, $BasePhotos.Count)]
  $extension = $source.Extension
  $newFilename = "seed-user-$UserId-$([Guid]::NewGuid().ToString('N'))$extension"
  $destination = Join-Path $UploadsPath $newFilename
  Copy-Item -LiteralPath $source.FullName -Destination $destination -Force

  Invoke-SqliteNonQuery -Connection $Connection -Transaction $Transaction -Sql @'
INSERT INTO photos (user_id, url, sort_order, is_primary, created_at)
VALUES (@user_id, @url, 0, 1, @created_at)
'@ -Parameters @{
    user_id = $UserId
    url = $newFilename
    created_at = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
  }
}

$sqliteDll = Find-SqliteDll
Add-Type -Path $sqliteDll

if (-not (Test-Path -LiteralPath $DatabasePath)) {
  throw "Database not found at $DatabasePath"
}

if (-not (Test-Path -LiteralPath $UploadsPath)) {
  New-Item -ItemType Directory -Path $UploadsPath | Out-Null
}

$rng = [System.Random]::new($RandomSeed)
$demoHash = New-WerkzeugPasswordHash -Password $DemoPassword -Rng $rng

$baseNames = @(
  'Shimon', 'Ronen', 'Aharon', 'Yuri', 'Dan', 'Gal', 'Yoni', 'Ran',
  'Noa', 'Maya', 'Eli', 'Tamar', 'Omer', 'Lior', 'Neta', 'Tal',
  'Adam', 'Yael', 'Amir', 'Dana', 'Aviv', 'Rona', 'Sagi', 'Eyal',
  'Hila', 'Niv', 'Rotem', 'Yoav', 'Inbar', 'Or', 'Dor', 'Shira',
  'Chen', 'Bar', 'Lana', 'Ziv', 'Tomer', 'Maor', 'Liza', 'Noga',
  'Idan', 'Eden', 'Ron', 'Aya', 'Gil', 'Keren', 'Nave', 'Rami',
  'Yuval', 'Kfir', 'Michal', 'Shai', 'Ofir', 'Talia', 'Benny', 'Lian',
  'Moran', 'Amitai', 'Ruth', 'Sivan', 'Dvir', 'Nir'
)

$basePhotos = Get-ChildItem -Path $UploadsPath -File | Where-Object { $_.Extension -in @('.png', '.jpg', '.jpeg', '.gif', '.webp') } | Select-Object -First 3
if ($null -eq $basePhotos -or $basePhotos.Count -lt 1) {
  throw "No base profile images found in $UploadsPath"
}

$connection = New-Object System.Data.SQLite.SQLiteConnection("Data Source=$DatabasePath;Version=3;")
$connection.Open()
$transaction = $connection.BeginTransaction()

try {
  Invoke-SqliteNonQuery -Connection $connection -Transaction $transaction -Sql 'PRAGMA foreign_keys = ON;'

  Invoke-SqliteNonQuery -Connection $connection -Transaction $transaction -Sql 'DELETE FROM messages;'
  Invoke-SqliteNonQuery -Connection $connection -Transaction $transaction -Sql 'DELETE FROM matches;'
  Invoke-SqliteNonQuery -Connection $connection -Transaction $transaction -Sql 'DELETE FROM swipes;'
  Invoke-SqliteNonQuery -Connection $connection -Transaction $transaction -Sql 'DELETE FROM preferences;'
  Invoke-SqliteNonQuery -Connection $connection -Transaction $transaction -Sql 'DELETE FROM photos;'
  Invoke-SqliteNonQuery -Connection $connection -Transaction $transaction -Sql 'DELETE FROM users;'
  Invoke-SqliteNonQuery -Connection $connection -Transaction $transaction -Sql "DELETE FROM sqlite_sequence WHERE name IN ('users', 'photos', 'preferences', 'swipes', 'matches', 'messages');"

  $users = New-Object System.Collections.Generic.List[hashtable]

  for ($i = 0; $i -lt $TargetUserCount; $i++) {
    $name = $baseNames[$i % $baseNames.Count]
    if ($i -ge $baseNames.Count) {
      $name = "$name$([int](1 + [Math]::Floor($i / $baseNames.Count)))"
    }

    $gender = New-Gender -Rng $rng
    $birthDate = New-BirthDate -Rng $rng
    $users.Add(@{
        id = $null
        email = ("{0}.{1}@meeting.local" -f ($name.ToLower() -replace '[^a-z0-9]+', ''), ($i + 1))
        display_name = $name
        password_hash = $demoHash
        birth_date = $birthDate
        gender = $gender
        bio = New-ProfileBio -Rng $rng -Name $name
        city = New-ProfileCity -Rng $rng
        created_at = (Get-Date).AddDays(-$rng.Next(5, 365)).ToString('yyyy-MM-dd HH:mm:ss')
        updated_at = (Get-Date).AddDays(-$rng.Next(0, 30)).ToString('yyyy-MM-dd HH:mm:ss')
    })
  }

  foreach ($user in $users) {
    Invoke-SqliteNonQuery -Connection $connection -Transaction $transaction -Sql @'
INSERT INTO users (email, password_hash, display_name, birth_date, gender, bio, city, created_at, updated_at)
VALUES (@email, @password_hash, @display_name, @birth_date, @gender, @bio, @city, @created_at, @updated_at)
'@ -Parameters $user

    $user['id'] = [int](Invoke-SqliteScalar -Connection $connection -Transaction $transaction -Sql 'SELECT last_insert_rowid();')
  }

  foreach ($user in $users) {
    $age = Get-Age $user['birth_date']
    $minAge = [Math]::Max(18, [Math]::Max(18, $age - $rng.Next(4, 10)))
    $maxAge = [Math]::Min(99, [Math]::Max($minAge + 1, $age + $rng.Next(3, 11)))
    $preference = New-Preference -Rng $rng -Gender $user['gender']

    Invoke-SqliteNonQuery -Connection $connection -Transaction $transaction -Sql @'
INSERT INTO preferences (user_id, gender_preference, current_age, min_age, max_age, created_at, updated_at)
VALUES (@user_id, @gender_preference, @current_age, @min_age, @max_age, @created_at, @updated_at)
'@ -Parameters @{
      user_id = $user['id']
      gender_preference = $preference
      current_age = $age
      min_age = $minAge
      max_age = $maxAge
      created_at = $user['created_at']
      updated_at = $user['updated_at']
    }
  }

  foreach ($user in $users) {
    Add-PhotoForUser -Connection $connection -Transaction $transaction -Rng $rng -UserId $user['id'] -BasePhotos $basePhotos -UploadsPath $UploadsPath
  }

  $pairCandidates = New-Object System.Collections.Generic.List[object]
  for ($a = 0; $a -lt $users.Count; $a++) {
    for ($b = $a + 1; $b -lt $users.Count; $b++) {
      $score = Get-MatchScore -UserA $users[$a] -UserB $users[$b]
      $pairCandidates.Add([pscustomobject]@{
          user1 = $users[$a]
          user2 = $users[$b]
          score = $score
      })
    }
  }

  $pairCandidates = $pairCandidates | Sort-Object score -Descending
  $matchPairs = New-Object System.Collections.Generic.List[object]
  $matchCountByUser = [System.Collections.Generic.Dictionary[int, int]]::new()
  foreach ($user in $users) {
    $matchCountByUser[$user['id']] = 0
  }

  foreach ($pair in $pairCandidates) {
    if ($pair.score -lt 50) {
      continue
    }
    if ($matchPairs.Count -ge 24) {
      break
    }
    if ($matchCountByUser[$pair.user1['id']] -ge 3 -or $matchCountByUser[$pair.user2['id']] -ge 3) {
      continue
    }

    $matchPairs.Add($pair)
    $matchCountByUser[$pair.user1['id']] = $matchCountByUser[$pair.user1['id']] + 1
    $matchCountByUser[$pair.user2['id']] = $matchCountByUser[$pair.user2['id']] + 1
  }

  $swipeKeys = New-Object System.Collections.Generic.HashSet[string]
  foreach ($pair in $matchPairs) {
    foreach ($direction in @(
      @{ swiper = $pair.user1; swiped = $pair.user2; is_like = 1 },
      @{ swiper = $pair.user2; swiped = $pair.user1; is_like = 1 }
    )) {
      $key = "$($direction['swiper']['id'])->$($direction['swiped']['id'])"
      if ($swipeKeys.Add($key)) {
        Invoke-SqliteNonQuery -Connection $connection -Transaction $transaction -Sql @'
INSERT INTO swipes (swiper_id, swiped_id, is_like, created_at)
VALUES (@swiper_id, @swiped_id, @is_like, @created_at)
'@ -Parameters @{
          swiper_id = $direction['swiper']['id']
          swiped_id = $direction['swiped']['id']
          is_like = $direction.is_like
          created_at = (Get-Date).AddDays(-$rng.Next(1, 120)).ToString('yyyy-MM-dd HH:mm:ss')
        }
      }
    }
  }

  foreach ($user in $users) {
    $targets = $users | Where-Object { $_['id'] -ne $user['id'] } | Get-Random -Count 6
    foreach ($target in $targets) {
      $key = "$($user['id'])->$($target['id'])"
      if ($swipeKeys.Contains($key)) {
        continue
      }

      $score = Get-MatchScore -UserA $user -UserB $target
      $isLike = if ($score -ge 75) { 1 } elseif ($score -ge 50) { if ($rng.NextDouble() -lt 0.65) { 1 } else { 0 } } else { if ($rng.NextDouble() -lt 0.25) { 1 } else { 0 } }
      if ($swipeKeys.Add($key)) {
        Invoke-SqliteNonQuery -Connection $connection -Transaction $transaction -Sql @'
INSERT INTO swipes (swiper_id, swiped_id, is_like, created_at)
VALUES (@swiper_id, @swiped_id, @is_like, @created_at)
'@ -Parameters @{
          swiper_id = $user['id']
          swiped_id = $target['id']
          is_like = $isLike
          created_at = (Get-Date).AddDays(-$rng.Next(1, 120)).ToString('yyyy-MM-dd HH:mm:ss')
        }
      }
    }
  }

  $matchBodies = @(
    'Hey, your profile made me smile. Want to grab coffee sometime?',
    'You seem fun. I would love to hear more about your weekend plans.',
    'I saw your photo and bio and thought we should say hello.',
    'This feels like a very good match. Want to keep chatting?',
    'You have great taste. Want to swap favorite spots in the city?',
    'I think we might get along well. Coffee or a walk soon?'
  )

  foreach ($pair in $matchPairs) {
    $matchedAt = (Get-Date).AddDays(-$rng.Next(1, 45))
    $matchCreated = $matchedAt.ToString('yyyy-MM-dd HH:mm:ss')
    Invoke-SqliteNonQuery -Connection $connection -Transaction $transaction -Sql @'
INSERT INTO matches (user1_id, user2_id, matched_at, is_active)
VALUES (@user1_id, @user2_id, @matched_at, 1)
'@ -Parameters @{
      user1_id = $pair.user1['id']
      user2_id = $pair.user2['id']
      matched_at = $matchCreated
    }

    $matchId = [int](Invoke-SqliteScalar -Connection $connection -Transaction $transaction -Sql 'SELECT last_insert_rowid();')
    $messageCount = $rng.Next(3, 8)
    $sender = $pair.user1
    for ($i = 0; $i -lt $messageCount; $i++) {
      if ($i -gt 0) {
        if ($sender['id'] -eq $pair.user1['id']) {
          $sender = $pair.user2
        } else {
          $sender = $pair.user1
        }
      }

      $body = $matchBodies[$rng.Next(0, $matchBodies.Count)]
      if ($i -eq 0) {
        $body = "Hi $($pair.user2['display_name']), $body"
        if ($sender['id'] -eq $pair.user2['id']) {
          $body = "Hi $($pair.user1['display_name']), $body"
        }
      } elseif ($i -eq 1) {
        $body = 'That sounds great. I am definitely interested.'
      } elseif ($i -eq 2) {
        $body = 'Perfect. Let us keep this going.'
      }

      Invoke-SqliteNonQuery -Connection $connection -Transaction $transaction -Sql @'
INSERT INTO messages (match_id, sender_id, body, sent_at, read_at)
VALUES (@match_id, @sender_id, @body, @sent_at, @read_at)
'@ -Parameters @{
        match_id = $matchId
        sender_id = $sender['id']
        body = $body
        sent_at = $matchedAt.AddMinutes(15 * $i + $rng.Next(1, 10)).ToString('yyyy-MM-dd HH:mm:ss')
        read_at = if ($rng.NextDouble() -lt 0.7) { $matchedAt.AddMinutes(30 * ($i + 1)).ToString('yyyy-MM-dd HH:mm:ss') } else { $null }
      }
    }
  }

  $transaction.Commit()
} catch {
  $transaction.Rollback()
  throw
} finally {
  $connection.Close()
}

$summaryConnection = New-Object System.Data.SQLite.SQLiteConnection("Data Source=$DatabasePath;Version=3;")
$summaryConnection.Open()
try {
  foreach ($table in @('users', 'photos', 'preferences', 'swipes', 'matches', 'messages')) {
    $count = Invoke-SqliteScalar -Connection $summaryConnection -Transaction $null -Sql "SELECT COUNT(*) FROM $table;"
    Write-Host ("{0}: {1}" -f $table, $count)
  }
  Write-Host ""
  Write-Host "Demo login password for seeded accounts: $DemoPassword"
} finally {
  $summaryConnection.Close()
}
