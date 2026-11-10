var builder = WebApplication.CreateBuilder(args);

builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

var app = builder.Build();

app.UseSwagger();
app.UseSwaggerUI();

app.MapGet("/", () => Results.Redirect("/swagger"));

app.MapPost("/api/mock", (MockVendorRequest? req) => Results.Ok(new { value = 1 }))
    .WithName("PostMockCalculation");

app.MapGet("/api/mock/value", () => Results.Ok(1))
    .WithName("GetMockValue");

app.MapGet("/health", () => Results.Ok(new { status = "Healthy" }))
    .WithName("HealthCheck");

app.Run();

record MockVendorRequest(int? Number1, int? Number2, int? Number3);
